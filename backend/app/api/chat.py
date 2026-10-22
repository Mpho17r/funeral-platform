"""Staff chat: direct messages and channels inside one business.

Every query is scoped to the caller's business, and a person only ever
sees conversations they are in. Message text is never copied into the
audit log.
"""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission
from app.models.chat import (
    ChatAttachment,
    ChatConversation,
    ChatMessage,
    ChatParticipant,
    ChatReaction,
)
from app.models.group import Group, GroupMember
from app.models.staff_presence import StaffPresence
from app.models.user import User
from app.services import chat_files, workspace_channels
from app.services.notifications import notify
from app.services.permission_service import has_permission

router = APIRouter(prefix="/chat", tags=["Staff Chat"])

MAX_BODY = 4000
MAX_PAGE = 100
EMOJI = {"👍", "❤️", "😂", "🙏", "✅", "😮"}


# ---- request bodies ---------------------------------------------------

class ConversationCreate(BaseModel):
    kind: str = Field(pattern="^(direct|channel)$")
    user_id: UUID | None = None          # direct
    name: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    user_ids: list[UUID] = []            # channel
    group_id: UUID | None = None         # channel from a group


class MessageCreate(BaseModel):
    body: str = Field(default="", max_length=MAX_BODY)
    reply_to_id: UUID | None = None
    mention_ids: list[UUID] = Field(default=[], max_length=50)
    attachment_ids: list[UUID] = Field(
        default=[], max_length=chat_files.MAX_PER_MESSAGE
    )


class ReactionToggle(BaseModel):
    emoji: str = Field(max_length=16)


class MessageEdit(BaseModel):
    body: str = Field(max_length=MAX_BODY)


class ParticipantsAdd(BaseModel):
    user_ids: list[UUID] = Field(min_length=1)


# ---- helpers ----------------------------------------------------------

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _clean(body: str) -> str:
    text = (body or "").strip()
    if not text:
        raise HTTPException(422, "Write a message first.")
    return text


def _active_users(db: Session, business_id, ids) -> dict:
    rows = (
        db.query(User)
        .filter(
            User.business_id == business_id,
            User.is_active.is_(True),
            User.id.in_(list(ids)),
        )
        .all()
    )
    return {u.id: u for u in rows}


def _membership(db: Session, user, conversation_id) -> tuple:
    """The conversation and the caller's seat in it, or 404."""

    row = (
        db.query(ChatConversation, ChatParticipant)
        .join(
            ChatParticipant,
            ChatParticipant.conversation_id == ChatConversation.id,
        )
        .filter(
            ChatConversation.id == conversation_id,
            ChatConversation.business_id == user["business_id"],
            ChatParticipant.user_id == user["user_id"],
        )
        .first()
    )
    if row is None:
        raise HTTPException(404, "Conversation not found.")
    return row


def _can_manage(db: Session, user: dict) -> bool:
    return has_permission(
        db,
        user_id=user["user_id"],
        role=user["role"],
        permission_key="chat.manage",
    )


def _message_out(
    m: ChatMessage,
    names: dict,
    reactions: list | None = None,
    attachments: list | None = None,
) -> dict:
    deleted = m.deleted_at is not None
    return {
        "id": str(m.id),
        "conversation_id": str(m.conversation_id),
        "sender_id": str(m.sender_id) if m.sender_id else None,
        "sender_name": names.get(m.sender_id, "Former colleague"),
        "kind": m.kind,
        "body": "" if deleted else m.body,
        "meta": None if deleted else m.meta,
        "mention_ids": [] if deleted else (m.meta or {}).get("mentions", []),
        "reply_to_id": str(m.reply_to_id) if m.reply_to_id else None,
        "created_at": m.created_at.isoformat(),
        "edited_at": m.edited_at.isoformat() if m.edited_at else None,
        "deleted": deleted,
        "reactions": [] if deleted else (reactions or []),
        "attachments": [] if deleted else (attachments or []),
    }


def _out_many(db: Session, user: dict, messages: list) -> list:
    """Messages with their senders, reactions and files filled in."""

    if not messages:
        return []

    names = _names(db, user["business_id"], [m.sender_id for m in messages])
    ids = [m.id for m in messages]

    reaction_rows = (
        db.query(ChatReaction)
        .filter(ChatReaction.message_id.in_(ids))
        .order_by(ChatReaction.created_at)
        .all()
    )
    by_message: dict = {}
    for r in reaction_rows:
        by_message.setdefault(r.message_id, {}).setdefault(
            r.emoji, []
        ).append(r.user_id)

    file_rows = (
        db.query(ChatAttachment)
        .filter(ChatAttachment.message_id.in_(ids))
        .order_by(ChatAttachment.created_at)
        .all()
    )
    files: dict = {}
    for f in file_rows:
        files.setdefault(f.message_id, []).append(_file_out(f))

    out = []
    for m in messages:
        grouped = by_message.get(m.id, {})
        reactions = [
            {
                "emoji": emoji,
                "count": len(users),
                "mine": user["user_id"] in users,
            }
            for emoji, users in grouped.items()
        ]
        out.append(_message_out(m, names, reactions, files.get(m.id, [])))

    return out


def _file_out(f: ChatAttachment) -> dict:
    return {
        "id": str(f.id),
        "filename": f.filename,
        "media_type": f.media_type,
        "size_bytes": f.size_bytes,
        "is_image": f.media_type in chat_files.IMAGE_TYPES,
    }


def _names(db: Session, business_id, ids) -> dict:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    return {
        u.id: u.full_name
        for u in db.query(User).filter(
            User.business_id == business_id, User.id.in_(ids)
        )
    }


def _unread(db: Session, conversation_id, me, since) -> int:
    return (
        db.query(func.count(ChatMessage.id))
        .filter(
            ChatMessage.conversation_id == conversation_id,
            ChatMessage.created_at > since,
            ChatMessage.deleted_at.is_(None),
            or_(
                ChatMessage.sender_id != me,
                ChatMessage.sender_id.is_(None),
            ),
        )
        .scalar()
        or 0
    )


def _unread_mentions(db: Session, conversation_id, me, since) -> int:
    return (
        db.query(func.count(ChatMessage.id))
        .filter(
            ChatMessage.conversation_id == conversation_id,
            ChatMessage.created_at > since,
            ChatMessage.deleted_at.is_(None),
            ChatMessage.meta["mentions"].contains([str(me)]),
        )
        .scalar()
        or 0
    )


def _conversation_out(db, user, conv, seat) -> dict:
    parts = (
        db.query(ChatParticipant.user_id)
        .filter(ChatParticipant.conversation_id == conv.id)
        .all()
    )
    part_ids = [p[0] for p in parts]
    names = _names(db, user["business_id"], part_ids)

    last = (
        db.query(ChatMessage)
        .filter(
            ChatMessage.conversation_id == conv.id,
            ChatMessage.deleted_at.is_(None),
        )
        .order_by(ChatMessage.created_at.desc())
        .first()
    )

    title = conv.name
    other_id = None
    if conv.kind == "direct":
        others = [p for p in part_ids if p != user["user_id"]]
        other_id = others[0] if others else None
        title = names.get(other_id, "Former colleague")

    return {
        "id": str(conv.id),
        "kind": conv.kind,
        "title": title,
        "description": conv.description,
        "group_id": str(conv.group_id) if conv.group_id else None,
        "system": conv.system_key is not None,
        "scope": (
            None
            if conv.system_key is None
            else "organisation"
            if conv.system_key == "org"
            else "branch"
        ),
        "other_user_id": str(other_id) if other_id else None,
        "participant_ids": [str(p) for p in part_ids],
        "participants": [
            {"id": str(p), "name": names.get(p, "Former colleague")}
            for p in part_ids
        ],
        "last_message": (
            {
                "body": (last.body or "📎 Attachment")[:140],
                "sender_name": names.get(last.sender_id)
                or _names(db, user["business_id"], [last.sender_id]).get(
                    last.sender_id, "Former colleague"
                ),
                "created_at": last.created_at.isoformat(),
            }
            if last
            else None
        ),
        "last_message_at": conv.last_message_at.isoformat(),
        "unread": _unread(db, conv.id, user["user_id"], seat.last_read_at),
        "mentioned": _unread_mentions(
            db, conv.id, user["user_id"], seat.last_read_at
        )
        > 0,
    }


# ---- people and conversations ----------------------------------------

@router.get("/people")
def people(
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("chat.use")),
):
    """Colleagues you can message, with whether they are around."""

    rows = (
        db.query(User, StaffPresence.status)
        .outerjoin(
            StaffPresence,
            and_(
                StaffPresence.user_id == User.id,
                StaffPresence.business_id == User.business_id,
            ),
        )
        .filter(
            User.business_id == user["business_id"],
            User.is_active.is_(True),
            User.id != user["user_id"],
        )
        .order_by(User.full_name)
        .all()
    )
    return [
        {
            "id": str(u.id),
            "name": u.full_name,
            "role": u.role,
            "job_title": getattr(u, "job_title", None),
            "status": presence or "offline",
        }
        for u, presence in rows
    ]


@router.get("/conversations")
def my_conversations(
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("chat.use")),
):
    # Make sure the organisation and branch channels exist and match the
    # team (also sets them up for businesses that existed before them).
    if workspace_channels.sync(db, user["business_id"]):
        db.commit()

    rows = (
        db.query(ChatConversation, ChatParticipant)
        .join(
            ChatParticipant,
            ChatParticipant.conversation_id == ChatConversation.id,
        )
        .filter(
            ChatConversation.business_id == user["business_id"],
            ChatParticipant.user_id == user["user_id"],
        )
        .order_by(ChatConversation.last_message_at.desc())
        .all()
    )
    return [_conversation_out(db, user, c, s) for c, s in rows]


@router.get("/unread-count")
def unread_count(
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("chat.use")),
):
    rows = (
        db.query(ChatParticipant)
        .join(
            ChatConversation,
            ChatConversation.id == ChatParticipant.conversation_id,
        )
        .filter(
            ChatConversation.business_id == user["business_id"],
            ChatParticipant.user_id == user["user_id"],
        )
        .all()
    )
    return {
        "unread": sum(
            _unread(db, s.conversation_id, user["user_id"], s.last_read_at)
            for s in rows
        ),
        "mentions": sum(
            _unread_mentions(
                db, s.conversation_id, user["user_id"], s.last_read_at
            )
            for s in rows
        ),
    }


def _add_participants(db, conv, ids, *, at=None):
    existing = {
        p[0]
        for p in db.query(ChatParticipant.user_id).filter(
            ChatParticipant.conversation_id == conv.id
        )
    }
    for uid in ids:
        if uid not in existing:
            db.add(
                ChatParticipant(
                    conversation_id=conv.id,
                    user_id=uid,
                    joined_at=at or _now(),
                    last_read_at=at or _now(),
                )
            )


@router.post("/conversations", status_code=status.HTTP_201_CREATED)
def create_conversation(
    payload: ConversationCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("chat.use")),
):
    biz, me = user["business_id"], user["user_id"]

    if payload.kind == "direct":
        if payload.user_id is None or payload.user_id == me:
            raise HTTPException(422, "Choose a colleague to message.")
        if payload.user_id not in _active_users(db, biz, [payload.user_id]):
            raise HTTPException(404, "Colleague not found.")

        key = ":".join(sorted([str(me), str(payload.user_id)]))
        conv = (
            db.query(ChatConversation)
            .filter(
                ChatConversation.business_id == biz,
                ChatConversation.direct_key == key,
            )
            .first()
        )
        if conv is None:
            conv = ChatConversation(
                business_id=biz, kind="direct", direct_key=key,
                created_by=me,
            )
            db.add(conv)
            db.flush()
            _add_participants(db, conv, [me, payload.user_id])
            db.commit()
        else:
            _add_participants(db, conv, [me, payload.user_id])
            db.commit()
    else:
        name = (payload.name or "").strip()
        ids = set(payload.user_ids)

        if payload.group_id is not None:
            group = (
                db.query(Group)
                .filter(
                    Group.id == payload.group_id, Group.business_id == biz
                )
                .first()
            )
            if group is None:
                raise HTTPException(404, "Group not found.")
            name = name or group.name
            ids |= {
                g[0]
                for g in db.query(GroupMember.user_id).filter(
                    GroupMember.group_id == group.id
                )
            }

        if not name:
            raise HTTPException(422, "Give the channel a name.")

        ids.add(me)
        found = _active_users(db, biz, ids)
        if set(found) != ids:
            raise HTTPException(404, "Someone you chose was not found.")

        conv = ChatConversation(
            business_id=biz, kind="channel", name=name,
            description=(payload.description or None),
            group_id=payload.group_id, created_by=me,
        )
        db.add(conv)
        db.flush()
        _add_participants(db, conv, ids)
        db.add(
            ChatMessage(
                business_id=biz, conversation_id=conv.id, sender_id=me,
                kind="system", body="created this channel",
            )
        )
        db.commit()

    row = _membership(db, user, conv.id)
    return _conversation_out(db, user, *row)


# ---- messages ---------------------------------------------------------

@router.get("/conversations/{conversation_id}/messages")
def list_messages(
    conversation_id: UUID,
    before: datetime | None = Query(default=None),
    after: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=MAX_PAGE),
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("chat.use")),
):
    """Newest page by default (oldest first). ``after`` fetches anything
    newer, which is how the screen polls; ``before`` pages backwards."""

    _membership(db, user, conversation_id)

    q = db.query(ChatMessage).filter(
        ChatMessage.conversation_id == conversation_id,
        ChatMessage.business_id == user["business_id"],
    )
    if after is not None:
        rows = (
            q.filter(ChatMessage.created_at > after)
            .order_by(ChatMessage.created_at)
            .limit(limit)
            .all()
        )
    else:
        if before is not None:
            q = q.filter(ChatMessage.created_at < before)
        rows = list(
            reversed(
                q.order_by(ChatMessage.created_at.desc()).limit(limit).all()
            )
        )

    return {
        "messages": _out_many(db, user, rows),
        "has_more": after is None and len(rows) == limit,
    }


@router.post(
    "/conversations/{conversation_id}/messages",
    status_code=status.HTTP_201_CREATED,
)
def send_message(
    conversation_id: UUID,
    payload: MessageCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("chat.use")),
):
    conv, seat = _membership(db, user, conversation_id)
    body = (payload.body or "").strip()

    if not body and not payload.attachment_ids:
        raise HTTPException(422, "Write a message first.")

    if payload.reply_to_id is not None:
        parent = (
            db.query(ChatMessage)
            .filter(
                ChatMessage.id == payload.reply_to_id,
                ChatMessage.conversation_id == conv.id,
            )
            .first()
        )
        if parent is None:
            raise HTTPException(404, "The message you replied to is gone.")

    mentions: list[str] = []
    if payload.mention_ids:
        wanted = set(payload.mention_ids)
        seated = {
            p[0]
            for p in db.query(ChatParticipant.user_id).filter(
                ChatParticipant.conversation_id == conv.id,
                ChatParticipant.user_id.in_(list(wanted)),
            )
        }
        if seated != wanted:
            raise HTTPException(
                422, "You can only mention people in this conversation."
            )
        mentions = sorted(str(i) for i in wanted if i != user["user_id"])

    files = []
    if payload.attachment_ids:
        files = (
            db.query(ChatAttachment)
            .filter(
                ChatAttachment.id.in_(payload.attachment_ids),
                ChatAttachment.conversation_id == conv.id,
                ChatAttachment.business_id == user["business_id"],
                ChatAttachment.uploaded_by == user["user_id"],
                ChatAttachment.message_id.is_(None),
            )
            .all()
        )
        if len(files) != len(set(payload.attachment_ids)):
            raise HTTPException(404, "An attached file was not found.")

    now = _now()
    message = ChatMessage(
        business_id=user["business_id"],
        conversation_id=conv.id,
        sender_id=user["user_id"],
        body=body,
        meta={"mentions": mentions} if mentions else None,
        reply_to_id=payload.reply_to_id,
        created_at=now,
    )
    db.add(message)
    db.flush()
    for f in files:
        f.message_id = message.id
    if mentions:
        who = db.query(User.full_name).filter(
            User.id == user["user_id"]
        ).scalar()
        notify(
            db,
            business_id=user["business_id"],
            user_ids=mentions,
            kind="mention",
            title=f"{who or 'Someone'} mentioned you",
            body=body[:200] or None,
            link="/staff",
            actor_id=user["user_id"],
        )
    conv.last_message_at = now
    seat.last_read_at = now
    db.commit()

    return _out_many(db, user, [message])[0]


def _own_message(db, user, message_id) -> ChatMessage:
    """A message in a conversation the caller is part of, or 404."""

    message = (
        db.query(ChatMessage)
        .join(
            ChatParticipant,
            and_(
                ChatParticipant.conversation_id
                == ChatMessage.conversation_id,
                ChatParticipant.user_id == user["user_id"],
            ),
        )
        .filter(
            ChatMessage.id == message_id,
            ChatMessage.business_id == user["business_id"],
        )
        .first()
    )
    if message is None:
        raise HTTPException(404, "Message not found.")
    return message


@router.patch("/messages/{message_id}")
def edit_message(
    message_id: UUID,
    payload: MessageEdit,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("chat.use")),
):
    message = _own_message(db, user, message_id)
    if message.sender_id != user["user_id"] or message.kind != "text":
        raise HTTPException(403, "You can only edit your own messages.")
    if message.deleted_at is not None:
        raise HTTPException(409, "That message was deleted.")

    message.body = _clean(payload.body)
    message.edited_at = _now()
    db.commit()

    return _out_many(db, user, [message])[0]


@router.delete("/messages/{message_id}", status_code=204)
def delete_message(
    message_id: UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("chat.use")),
):
    message = _own_message(db, user, message_id)
    mine = message.sender_id == user["user_id"]

    if not mine and not _can_manage(db, user):
        raise HTTPException(403, "You can only delete your own messages.")

    if message.deleted_at is None:
        message.deleted_at = _now()
        gone = (
            db.query(ChatAttachment)
            .filter(ChatAttachment.message_id == message.id)
            .all()
        )
        for f in gone:
            chat_files.remove(f.business_id, f.id)
            db.delete(f)
        db.commit()


@router.post("/conversations/{conversation_id}/read", status_code=204)
def mark_read(
    conversation_id: UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("chat.use")),
):
    _, seat = _membership(db, user, conversation_id)
    seat.last_read_at = _now()
    db.commit()


# ---- members of a channel --------------------------------------------

@router.post("/conversations/{conversation_id}/participants")
def add_participants(
    conversation_id: UUID,
    payload: ParticipantsAdd,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("chat.use")),
):
    conv, _ = _membership(db, user, conversation_id)
    if conv.kind != "channel":
        raise HTTPException(409, "People can only be added to a channel.")
    if conv.system_key:
        raise HTTPException(
            409,
            "This channel keeps its members up to date automatically.",
        )

    ids = set(payload.user_ids)
    if set(_active_users(db, user["business_id"], ids)) != ids:
        raise HTTPException(404, "Someone you chose was not found.")

    _add_participants(db, conv, ids)
    db.commit()

    return _conversation_out(db, user, *_membership(db, user, conv.id))


@router.delete(
    "/conversations/{conversation_id}/participants/{user_id}",
    status_code=204,
)
def remove_participant(
    conversation_id: UUID,
    user_id: UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("chat.use")),
):
    conv, _ = _membership(db, user, conversation_id)
    if conv.kind != "channel":
        raise HTTPException(409, "You cannot leave a direct message.")
    if conv.system_key:
        raise HTTPException(
            409,
            "This channel keeps its members up to date automatically.",
        )

    if user_id != user["user_id"] and not _can_manage(db, user):
        raise HTTPException(403, "You can only remove yourself.")

    db.query(ChatParticipant).filter(
        ChatParticipant.conversation_id == conv.id,
        ChatParticipant.user_id == user_id,
    ).delete()
    db.commit()


# ---- reactions --------------------------------------------------------

@router.post("/messages/{message_id}/reactions")
def toggle_reaction(
    message_id: UUID,
    payload: ReactionToggle,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("chat.use")),
):
    """React with an emoji, or take your reaction back."""

    if payload.emoji not in EMOJI:
        raise HTTPException(422, "That reaction is not available.")

    message = _own_message(db, user, message_id)
    if message.deleted_at is not None:
        raise HTTPException(409, "That message was deleted.")

    existing = (
        db.query(ChatReaction)
        .filter(
            ChatReaction.message_id == message.id,
            ChatReaction.user_id == user["user_id"],
            ChatReaction.emoji == payload.emoji,
        )
        .first()
    )
    if existing is None:
        db.add(
            ChatReaction(
                message_id=message.id,
                user_id=user["user_id"],
                emoji=payload.emoji,
            )
        )
    else:
        db.delete(existing)
    db.commit()

    return _out_many(db, user, [message])[0]["reactions"]


# ---- files ------------------------------------------------------------

@router.post(
    "/conversations/{conversation_id}/attachments",
    status_code=status.HTTP_201_CREATED,
)
async def upload_attachment(
    conversation_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("chat.use")),
):
    """Upload a file; send it by naming its id when posting a message."""

    conv, _ = _membership(db, user, conversation_id)

    contents = await file.read(chat_files.MAX_BYTES + 1)
    name = chat_files.clean_name(file.filename)

    try:
        media_type = chat_files.detect(name, contents)
    except chat_files.ChatFileError as error:
        raise HTTPException(400, str(error))

    attachment = ChatAttachment(
        business_id=user["business_id"],
        conversation_id=conv.id,
        uploaded_by=user["user_id"],
        filename=name,
        media_type=media_type,
        size_bytes=len(contents),
    )
    db.add(attachment)
    db.flush()
    chat_files.save(user["business_id"], attachment.id, contents)
    db.commit()

    return _file_out(attachment)


@router.get("/attachments/{attachment_id}")
def download_attachment(
    attachment_id: UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("chat.use")),
):
    row = (
        db.query(ChatAttachment)
        .join(
            ChatParticipant,
            and_(
                ChatParticipant.conversation_id
                == ChatAttachment.conversation_id,
                ChatParticipant.user_id == user["user_id"],
            ),
        )
        .join(ChatMessage, ChatMessage.id == ChatAttachment.message_id)
        .filter(
            ChatAttachment.id == attachment_id,
            ChatAttachment.business_id == user["business_id"],
            ChatMessage.deleted_at.is_(None),
        )
        .first()
    )
    path = (
        chat_files.locate(row.business_id, row.id) if row is not None else None
    )
    if row is None or path is None:
        raise HTTPException(404, "File not found.")

    inline = row.media_type in chat_files.IMAGE_TYPES

    return FileResponse(
        path,
        media_type=row.media_type,
        filename=row.filename,
        content_disposition_type="inline" if inline else "attachment",
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, max-age=300",
        },
    )
