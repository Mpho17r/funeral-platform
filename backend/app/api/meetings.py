"""Meetings and instant calls for staff.

A meeting has a time, an agenda and a join link, and invitees who can
accept or decline. Posting it into a chat shows it there as a card.
Calls use a link on the configured call server; nothing is recorded.
"""

import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.chat import (
    _active_users,
    _membership,
    _names,
    _now,
)
from app.config import settings
from app.database import get_db
from app.dependencies.roles import require_permission
from app.models.chat import ChatConversation, ChatMessage, ChatParticipant
from app.models.meeting import Meeting, MeetingInvitee
from app.services.notifications import notify

router = APIRouter(prefix="/meetings", tags=["Meetings"])

MAX_HOURS = 24


class MeetingCreate(BaseModel):
    title: str = Field(min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=2000)
    starts_at: datetime
    ends_at: datetime
    join_url: str | None = Field(default=None, max_length=500)
    make_call_link: bool = False
    user_ids: list[UUID] = []
    conversation_id: UUID | None = None


class MeetingEdit(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=2000)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    join_url: str | None = Field(default=None, max_length=500)
    add_user_ids: list[UUID] = []


class Respond(BaseModel):
    response: str = Field(pattern="^(accepted|declined)$")


class Huddle(BaseModel):
    conversation_id: UUID


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _clean_url(url: str | None) -> str | None:
    url = (url or "").strip()
    if not url:
        return None
    if not url.lower().startswith("https://") or " " in url:
        raise HTTPException(
            422, "The join link must be a web address starting with https://"
        )
    return url


def _new_call_link() -> str:
    base = settings.call_base_url.rstrip("/")
    return f"{base}/FuneralOS-{secrets.token_urlsafe(12)}"


def _check_times(starts: datetime, ends: datetime) -> tuple[datetime, datetime]:
    starts, ends = _aware(starts), _aware(ends)
    if ends <= starts:
        raise HTTPException(422, "The meeting must end after it starts.")
    if ends - starts > timedelta(hours=MAX_HOURS):
        raise HTTPException(422, "A meeting can be at most 24 hours long.")
    return starts, ends


def _out(db: Session, user: dict, m: Meeting) -> dict:
    invitees = (
        db.query(MeetingInvitee)
        .filter(MeetingInvitee.meeting_id == m.id)
        .all()
    )
    names = _names(
        db,
        user["business_id"],
        [i.user_id for i in invitees] + [m.organizer_id],
    )
    mine = next(
        (i.response for i in invitees if i.user_id == user["user_id"]),
        None,
    )
    return {
        "id": str(m.id),
        "title": m.title,
        "description": m.description,
        "starts_at": m.starts_at.isoformat(),
        "ends_at": m.ends_at.isoformat(),
        "join_url": m.join_url,
        "organizer_id": str(m.organizer_id) if m.organizer_id else None,
        "organizer_name": names.get(m.organizer_id, "Former colleague"),
        "conversation_id": (
            str(m.conversation_id) if m.conversation_id else None
        ),
        "cancelled": m.cancelled_at is not None,
        "my_response": mine,
        "is_organizer": m.organizer_id == user["user_id"],
        "invitees": [
            {
                "id": str(i.user_id),
                "name": names.get(i.user_id, "Former colleague"),
                "response": i.response,
            }
            for i in invitees
        ],
    }


def _conflicts(db, business_id, user_ids, starts, ends, skip=None) -> list:
    rows = (
        db.query(Meeting, MeetingInvitee.user_id)
        .join(MeetingInvitee, MeetingInvitee.meeting_id == Meeting.id)
        .filter(
            Meeting.business_id == business_id,
            Meeting.cancelled_at.is_(None),
            Meeting.starts_at < ends,
            Meeting.ends_at > starts,
            MeetingInvitee.user_id.in_(list(user_ids)),
            MeetingInvitee.response != "declined",
        )
        .all()
    )
    names = _names(db, business_id, [u for _, u in rows])
    return [
        {"user_name": names.get(u, ""), "title": m.title}
        for m, u in rows
        if m.id != skip
    ]


def _get_visible(db: Session, user: dict, meeting_id: UUID) -> Meeting:
    m = (
        db.query(Meeting)
        .outerjoin(MeetingInvitee, MeetingInvitee.meeting_id == Meeting.id)
        .filter(
            Meeting.id == meeting_id,
            Meeting.business_id == user["business_id"],
            or_(
                Meeting.organizer_id == user["user_id"],
                MeetingInvitee.user_id == user["user_id"],
            ),
        )
        .first()
    )
    if m is None:
        raise HTTPException(404, "Meeting not found.")
    return m


def _post_card(db, m: Meeting, kind: str, body: str):
    if m.conversation_id is None:
        return
    now = _now()
    db.add(
        ChatMessage(
            business_id=m.business_id,
            conversation_id=m.conversation_id,
            sender_id=m.organizer_id,
            kind=kind,
            body=body,
            meta={
                "meeting_id": str(m.id),
                "title": m.title,
                "starts_at": m.starts_at.isoformat(),
                "ends_at": m.ends_at.isoformat(),
                "join_url": m.join_url,
            },
            created_at=now,
        )
    )
    conv = db.get(ChatConversation, m.conversation_id)
    if conv:
        conv.last_message_at = now


# ---- endpoints --------------------------------------------------------

@router.post("", status_code=status.HTTP_201_CREATED)
def create_meeting(
    payload: MeetingCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("meetings.use")),
):
    biz, me = user["business_id"], user["user_id"]
    starts, ends = _check_times(payload.starts_at, payload.ends_at)

    if starts < _now() - timedelta(minutes=5):
        raise HTTPException(422, "A meeting cannot start in the past.")

    ids = set(payload.user_ids)

    if payload.conversation_id is not None:
        conv, _ = _membership(db, user, payload.conversation_id)
        ids |= {
            p[0]
            for p in db.query(ChatParticipant.user_id).filter(
                ChatParticipant.conversation_id == conv.id
            )
        }

    ids.discard(me)
    if set(_active_users(db, biz, ids)) != ids:
        raise HTTPException(404, "Someone you invited was not found.")

    url = _clean_url(payload.join_url)
    if url is None and payload.make_call_link:
        url = _new_call_link()

    meeting = Meeting(
        business_id=biz,
        organizer_id=me,
        conversation_id=payload.conversation_id,
        title=payload.title.strip(),
        description=(payload.description or "").strip() or None,
        starts_at=starts,
        ends_at=ends,
        join_url=url,
    )
    db.add(meeting)
    db.flush()

    db.add(MeetingInvitee(meeting_id=meeting.id, user_id=me,
                          response="accepted"))
    for uid in ids:
        db.add(MeetingInvitee(meeting_id=meeting.id, user_id=uid))

    _post_card(db, meeting, "meeting", "scheduled a meeting")
    db.flush()
    notify(
        db,
        business_id=biz,
        user_ids=ids,
        kind="meeting_invite",
        title=f"Meeting invite: {meeting.title}",
        body=starts.strftime("%a %d %b, %H:%M UTC"),
        link="/staff",
        actor_id=me,
    )
    clashes = _conflicts(db, biz, ids | {me}, starts, ends, skip=meeting.id)
    db.commit()

    body = _out(db, user, meeting)
    body["conflicts"] = clashes
    return body


@router.get("")
def list_meetings(
    scope: str = Query(default="upcoming", pattern="^(upcoming|past)$"),
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("meetings.use")),
):
    now = _now()
    q = (
        db.query(Meeting)
        .outerjoin(MeetingInvitee, MeetingInvitee.meeting_id == Meeting.id)
        .filter(
            Meeting.business_id == user["business_id"],
            or_(
                Meeting.organizer_id == user["user_id"],
                MeetingInvitee.user_id == user["user_id"],
            ),
        )
        .distinct()
    )
    if scope == "upcoming":
        q = q.filter(Meeting.ends_at >= now).order_by(Meeting.starts_at)
    else:
        q = q.filter(Meeting.ends_at < now).order_by(
            Meeting.starts_at.desc()
        )
    return [_out(db, user, m) for m in q.limit(100).all()]


@router.get("/{meeting_id}")
def get_meeting(
    meeting_id: UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("meetings.use")),
):
    return _out(db, user, _get_visible(db, user, meeting_id))


@router.patch("/{meeting_id}")
def edit_meeting(
    meeting_id: UUID,
    payload: MeetingEdit,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("meetings.use")),
):
    m = _get_visible(db, user, meeting_id)
    if m.organizer_id != user["user_id"]:
        raise HTTPException(403, "Only the organizer can change a meeting.")
    if m.cancelled_at is not None:
        raise HTTPException(409, "This meeting was cancelled.")

    data = payload.model_dump(exclude_unset=True)
    retime = "starts_at" in data or "ends_at" in data

    if retime:
        starts, ends = _check_times(
            data.get("starts_at") or m.starts_at,
            data.get("ends_at") or m.ends_at,
        )
        m.starts_at, m.ends_at = starts, ends
    if "title" in data and data["title"]:
        m.title = data["title"].strip()
    if "description" in data:
        m.description = (data["description"] or "").strip() or None
    if "join_url" in data:
        m.join_url = _clean_url(data["join_url"])

    new_ids = set(payload.add_user_ids)
    if new_ids:
        if set(_active_users(db, user["business_id"], new_ids)) != new_ids:
            raise HTTPException(404, "Someone you invited was not found.")
        have = {
            i[0]
            for i in db.query(MeetingInvitee.user_id).filter(
                MeetingInvitee.meeting_id == m.id
            )
        }
        for uid in new_ids - have:
            db.add(MeetingInvitee(meeting_id=m.id, user_id=uid))
        notify(
            db,
            business_id=user["business_id"],
            user_ids=new_ids - have,
            kind="meeting_invite",
            title=f"Meeting invite: {m.title}",
            link="/staff",
            actor_id=user["user_id"],
        )

    if retime:
        # A new time needs everyone to say yes again.
        db.query(MeetingInvitee).filter(
            MeetingInvitee.meeting_id == m.id,
            MeetingInvitee.user_id != m.organizer_id,
        ).update({"response": "pending"})
        _post_card(db, m, "meeting", "changed the time of a meeting")
        notify(
            db,
            business_id=user["business_id"],
            user_ids=[
                i[0]
                for i in db.query(MeetingInvitee.user_id).filter(
                    MeetingInvitee.meeting_id == m.id
                )
            ],
            kind="meeting_changed",
            title=f"Meeting time changed: {m.title}",
            body="Please accept the new time.",
            link="/staff",
            actor_id=user["user_id"],
        )

    db.commit()
    return _out(db, user, m)


@router.post("/{meeting_id}/cancel")
def cancel_meeting(
    meeting_id: UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("meetings.use")),
):
    m = _get_visible(db, user, meeting_id)
    if m.organizer_id != user["user_id"]:
        raise HTTPException(403, "Only the organizer can cancel a meeting.")

    if m.cancelled_at is None:
        m.cancelled_at = _now()
        _post_card(db, m, "meeting", "cancelled a meeting")
        db.commit()

    return _out(db, user, m)


@router.post("/{meeting_id}/respond")
def respond(
    meeting_id: UUID,
    payload: Respond,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("meetings.use")),
):
    m = _get_visible(db, user, meeting_id)
    seat = (
        db.query(MeetingInvitee)
        .filter(
            MeetingInvitee.meeting_id == m.id,
            MeetingInvitee.user_id == user["user_id"],
        )
        .first()
    )
    if seat is None:
        raise HTTPException(404, "You were not invited to this meeting.")
    if m.cancelled_at is not None:
        raise HTTPException(409, "This meeting was cancelled.")

    seat.response = payload.response
    db.commit()
    return _out(db, user, m)


@router.post("/huddle", status_code=status.HTTP_201_CREATED)
def start_huddle(
    payload: Huddle,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("meetings.use")),
):
    """Post a call link into a chat so everyone there can join now."""

    conv, seat = _membership(db, user, payload.conversation_id)
    now = _now()
    url = _new_call_link()

    message = ChatMessage(
        business_id=user["business_id"],
        conversation_id=conv.id,
        sender_id=user["user_id"],
        kind="call",
        body="started a call",
        meta={"join_url": url},
        created_at=now,
    )
    db.add(message)
    conv.last_message_at = now
    seat.last_read_at = now
    db.commit()

    return {"join_url": url, "message_id": str(message.id)}
