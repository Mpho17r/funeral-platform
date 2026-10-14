from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission

from app.models.business import Business
from app.models.communication import (
    CommunicationMessage,
    MemberCommunicationPreference,
    MessageTemplate,
    REMINDER_KINDS,
)
from app.models.member import Member
from app.models.membership import Membership
from app.schemas.communication import (
    CustomMessageCreate,
    MessageCancel,
    MessageListResponse,
    MessageResponse,
    PlaceholderInfo,
    PreferenceResponse,
    PreferenceUpdate,
    ReminderGenerateResponse,
    ReminderOptions,
    ReminderPlanResponse,
    TemplateListResponse,
    TemplateResponse,
    TemplateUpdate,
)
from app.services.audit_service import (
    build_audit_changes,
    create_audit_log,
    snapshot_fields,
)
from app.services.communications import (
    DEFAULT_CHANNEL,
    PLACEHOLDERS,
    ReminderPlan,
    action_url,
    load_templates,
    pick_channel,
    plan_reminders,
    queue_candidates,
    unknown_placeholders,
)


router = APIRouter(
    tags=["Communications"],
)


AUDITED_PREFERENCE_FIELDS = (
    "preferred_channel",
    "opted_out",
    "opt_out_reason",
)

AUDITED_TEMPLATE_FIELDS = ("subject", "body", "is_active")


def get_business_id(current_user: dict) -> UUID:
    business_id = current_user.get("business_id")

    if not business_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not associated with a business",
        )

    return UUID(str(business_id))


def get_user_id(current_user: dict) -> UUID:
    return UUID(str(current_user["user_id"]))


def get_business_or_404(db: Session, business_id: UUID) -> Business:
    business = db.get(Business, business_id)

    if business is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found",
        )

    return business


def get_member_or_404(
    db: Session,
    member_id: UUID,
    business_id: UUID,
) -> Member:
    member = (
        db.query(Member)
        .filter(
            Member.id == member_id,
            Member.business_id == business_id,
        )
        .first()
    )

    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found",
        )

    return member


def get_message_or_404(
    db: Session,
    message_id: UUID,
    business_id: UUID,
) -> CommunicationMessage:
    message = (
        db.query(CommunicationMessage)
        .filter(
            CommunicationMessage.id == message_id,
            CommunicationMessage.business_id == business_id,
        )
        .with_for_update()
        .first()
    )

    if message is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found",
        )

    return message


def member_name(member: Member | None) -> str | None:
    if member is None:
        return None

    return f"{member.first_name} {member.last_name}".strip()


def message_response(
    message: CommunicationMessage,
    member: Member | None,
    membership: Membership | None,
) -> MessageResponse:
    return MessageResponse(
        id=message.id,
        member_id=message.member_id,
        member_name=member_name(member),
        membership_id=message.membership_id,
        membership_number=(
            membership.membership_number if membership else None
        ),
        kind=message.kind,
        channel=message.channel,
        recipient=message.recipient,
        subject=message.subject,
        body=message.body,
        status=message.status,
        action_url=action_url(message),
        created_at=message.created_at,
        sent_at=message.sent_at,
        cancelled_at=message.cancelled_at,
        cancel_reason=message.cancel_reason,
    )


def load_message_response(
    db: Session,
    message: CommunicationMessage,
) -> MessageResponse:
    member = db.get(Member, message.member_id)
    membership = (
        db.get(Membership, message.membership_id)
        if message.membership_id
        else None
    )

    return message_response(message, member, membership)


def audit_message(
    db: Session,
    *,
    message: CommunicationMessage,
    current_user: dict,
    action: str,
    notes: str,
    extra: dict | None = None,
) -> None:
    # The wording and the recipient are personal, so the audit trail
    # records which message it was, not what it said.
    details = {
        "kind": message.kind,
        "channel": message.channel,
        "member_id": str(message.member_id),
        "membership_id": (
            str(message.membership_id) if message.membership_id else None
        ),
    }

    if extra:
        details.update(extra)

    create_audit_log(
        db,
        business_id=message.business_id,
        user_id=get_user_id(current_user),
        action=action,
        entity_type="communication_message",
        entity_id=message.id,
        details=details,
        notes=notes,
    )


# ============================================================
# TEMPLATES
# ============================================================

def template_responses(db: Session, business_id: UUID):
    return [
        TemplateResponse(
            kind=view.kind,
            subject=view.subject,
            body=view.body,
            is_active=view.is_active,
            is_default=view.is_default,
        )
        for view in load_templates(db, business_id).values()
    ]


@router.get(
    "/communications/templates",
    response_model=TemplateListResponse,
)
def list_templates(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("communications.view")),
):
    business_id = get_business_id(current_user)

    return TemplateListResponse(
        templates=template_responses(db, business_id),
        placeholders=[
            PlaceholderInfo(name=name, description=description)
            for name, description in PLACEHOLDERS.items()
        ],
    )


@router.put(
    "/communications/templates/{kind}",
    response_model=TemplateResponse,
)
def update_template(
    kind: str,
    data: TemplateUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_permission("communications.templates")
    ),
):
    business_id = get_business_id(current_user)

    if kind not in REMINDER_KINDS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    unknown = unknown_placeholders(data.subject) + unknown_placeholders(
        data.body
    )

    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "Unknown placeholder: "
                + ", ".join(f"{{{name}}}" for name in sorted(set(unknown)))
            ),
        )

    current = load_templates(db, business_id)[kind]

    row = (
        db.query(MessageTemplate)
        .filter(
            MessageTemplate.business_id == business_id,
            MessageTemplate.kind == kind,
        )
        .with_for_update()
        .first()
    )

    old_values = {
        "subject": current.subject,
        "body": current.body,
        "is_active": current.is_active,
    }

    if row is None:
        row = MessageTemplate(
            business_id=business_id,
            kind=kind,
            subject=data.subject,
            body=data.body,
            is_active=data.is_active,
            updated_by=get_user_id(current_user),
        )
        db.add(row)
    else:
        row.subject = data.subject
        row.body = data.body
        row.is_active = data.is_active
        row.updated_by = get_user_id(current_user)

    changes = build_audit_changes(
        old_values,
        {
            "subject": data.subject,
            "body": data.body,
            "is_active": data.is_active,
        },
    )

    if changes:
        create_audit_log(
            db,
            business_id=business_id,
            user_id=get_user_id(current_user),
            action="communication_template.updated",
            entity_type="message_template",
            details={"kind": kind, "changes": changes},
            notes="Message template was updated.",
        )

    db.commit()

    return template_responses_for(db, business_id, kind)


def template_responses_for(db: Session, business_id: UUID, kind: str):
    return next(
        response
        for response in template_responses(db, business_id)
        if response.kind == kind
    )


# ============================================================
# MEMBER PREFERENCES
# ============================================================

def preference_response(
    member_id: UUID,
    row: MemberCommunicationPreference | None,
) -> PreferenceResponse:
    if row is None:
        return PreferenceResponse(
            member_id=member_id,
            preferred_channel=DEFAULT_CHANNEL,
            opted_out=False,
            opted_out_at=None,
            opt_out_reason=None,
        )

    return PreferenceResponse(
        member_id=member_id,
        preferred_channel=row.preferred_channel,
        opted_out=row.opted_out,
        opted_out_at=row.opted_out_at,
        opt_out_reason=row.opt_out_reason,
    )


@router.get(
    "/members/{member_id}/communication-preferences",
    response_model=PreferenceResponse,
)
def read_preferences(
    member_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("communications.view")),
):
    business_id = get_business_id(current_user)
    get_member_or_404(db, member_id, business_id)

    row = db.get(MemberCommunicationPreference, member_id)

    return preference_response(member_id, row)


@router.patch(
    "/members/{member_id}/communication-preferences",
    response_model=PreferenceResponse,
)
def update_preferences(
    member_id: UUID,
    data: PreferenceUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("communications.send")),
):
    business_id = get_business_id(current_user)
    get_member_or_404(db, member_id, business_id)

    updates = data.model_dump(exclude_unset=True)

    row = (
        db.query(MemberCommunicationPreference)
        .filter(MemberCommunicationPreference.member_id == member_id)
        .with_for_update()
        .first()
    )

    created = row is None

    if row is None:
        row = MemberCommunicationPreference(
            member_id=member_id,
            business_id=business_id,
            preferred_channel=DEFAULT_CHANNEL,
            opted_out=False,
        )
        db.add(row)
        db.flush()

    if updates.get("preferred_channel") is None:
        updates.pop("preferred_channel", None)

    if updates.get("opted_out") is None:
        updates.pop("opted_out", None)

    old_values = snapshot_fields(row, AUDITED_PREFERENCE_FIELDS)

    if "opted_out" in updates:
        if updates["opted_out"] and not row.opted_out:
            row.opted_out_at = datetime.now(timezone.utc)
        elif not updates["opted_out"]:
            row.opted_out_at = None
            # Opting back in clears the old reason.
            updates["opt_out_reason"] = None

    elif "opt_out_reason" in updates and not row.opted_out:
        # A reason only makes sense for someone who has opted out.
        updates.pop("opt_out_reason")

    for field, value in updates.items():
        setattr(row, field, value)

    row.updated_by = get_user_id(current_user)

    changes = build_audit_changes(
        old_values,
        snapshot_fields(row, AUDITED_PREFERENCE_FIELDS),
    )

    if changes or created:
        create_audit_log(
            db,
            business_id=business_id,
            user_id=get_user_id(current_user),
            action="communication_preferences.updated",
            entity_type="member",
            entity_id=member_id,
            details={"changes": changes},
            notes="Member communication preferences were updated.",
        )

    db.commit()
    db.refresh(row)

    return preference_response(member_id, row)


# ============================================================
# REMINDER RUN
# ============================================================

def plan_response(plan: ReminderPlan, db: Session) -> dict:
    items = [
        {
            "kind": candidate.kind,
            "member_id": candidate.member.id,
            "member_name": member_name(candidate.member),
            "membership_id": candidate.membership.id,
            "membership_number": candidate.membership.membership_number,
            "channel": candidate.channel,
            "recipient": candidate.recipient,
            "subject": candidate.subject,
            "body": candidate.body,
        }
        for candidate in plan.candidates
    ]

    counts: dict[str, int] = {}

    for candidate in plan.candidates:
        counts[candidate.kind] = counts.get(candidate.kind, 0) + 1

    return {
        "date": plan.today.isoformat(),
        "items": items,
        "skipped": [
            {
                "kind": skipped.kind,
                "member_id": skipped.member_id,
                "member_name": skipped.member_name,
                "membership_number": skipped.membership_number,
                "reason": skipped.reason,
            }
            for skipped in plan.skipped
        ],
        "already_queued": plan.already_queued,
        "disabled_kinds": plan.disabled_kinds,
        "counts": counts,
    }


def build_plan(
    db: Session,
    business_id: UUID,
    options: ReminderOptions,
) -> ReminderPlan:
    business = get_business_or_404(db, business_id)

    return plan_reminders(
        db,
        business,
        kinds=options.kinds,
        branch_id=options.branch_id,
        days_before=options.days_before,
        warning_days=options.warning_days,
        overdue_repeat_days=options.overdue_repeat_days,
        lapsed_notice_days=options.lapsed_notice_days,
    )


@router.post(
    "/communications/reminders/preview",
    response_model=ReminderPlanResponse,
)
def preview_reminders(
    options: ReminderOptions | None = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("communications.view")),
):
    business_id = get_business_id(current_user)

    plan = build_plan(db, business_id, options or ReminderOptions())

    return plan_response(plan, db)


@router.post(
    "/communications/reminders/generate",
    response_model=ReminderGenerateResponse,
)
def generate_reminders(
    options: ReminderOptions | None = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("communications.send")),
):
    business_id = get_business_id(current_user)

    plan = build_plan(db, business_id, options or ReminderOptions())

    created, duplicates = queue_candidates(
        db,
        business_id,
        get_user_id(current_user),
        plan.candidates,
    )

    plan.already_queued += duplicates

    counts: dict[str, int] = {}

    for message in created:
        counts[message.kind] = counts.get(message.kind, 0) + 1

    if created:
        create_audit_log(
            db,
            business_id=business_id,
            user_id=get_user_id(current_user),
            action="communication.reminders_generated",
            entity_type="communication_message",
            details={
                "created": len(created),
                "counts": counts,
                "skipped": len(plan.skipped),
                "date": plan.today.isoformat(),
            },
            notes="Payment and membership reminders were queued.",
        )

    db.commit()

    response = plan_response(plan, db)

    # Only what was actually written.
    created_ids = {message.dedupe_key for message in created}
    response["items"] = [
        item
        for item, candidate in zip(response["items"], plan.candidates)
        if candidate.dedupe_key in created_ids
    ]
    response["counts"] = counts
    response["created"] = len(created)

    return response


# ============================================================
# MESSAGES
# ============================================================

@router.get(
    "/communications/messages",
    response_model=MessageListResponse,
)
def list_messages(
    message_status: str | None = Query(default=None, alias="status"),
    kind: str | None = None,
    member_id: UUID | None = None,
    branch_id: UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("communications.view")),
):
    business_id = get_business_id(current_user)

    base = (
        select(CommunicationMessage)
        .join(Member, Member.id == CommunicationMessage.member_id)
        .where(CommunicationMessage.business_id == business_id)
    )

    if kind is not None:
        base = base.where(CommunicationMessage.kind == kind)

    if member_id is not None:
        base = base.where(CommunicationMessage.member_id == member_id)

    if branch_id is not None:
        base = base.where(Member.branch_id == branch_id)

    # Counts by status ignore the status filter, so the tabs on the
    # screen can show how many are in each.
    counts = {"queued": 0, "sent": 0, "cancelled": 0}

    filtered = base.subquery()

    for row_status, total in db.execute(
        select(filtered.c.status, func.count()).group_by(
            filtered.c.status
        )
    ).all():
        counts[row_status] = total

    if message_status is not None:
        if message_status not in counts:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Status must be queued, sent or cancelled",
            )

        base = base.where(CommunicationMessage.status == message_status)

    total = db.scalar(select(func.count()).select_from(base.subquery()))

    # Oldest first for the queue so nothing is forgotten; newest first
    # for history.
    order = (
        CommunicationMessage.created_at.asc()
        if message_status == "queued"
        else CommunicationMessage.created_at.desc()
    )

    messages = db.scalars(
        base.order_by(order, CommunicationMessage.id)
        .limit(limit)
        .offset(offset)
    ).all()

    members = {
        member.id: member
        for member in db.scalars(
            select(Member).where(
                Member.id.in_({message.member_id for message in messages})
            )
        ).all()
    }
    memberships = {
        membership.id: membership
        for membership in db.scalars(
            select(Membership).where(
                Membership.id.in_(
                    {
                        message.membership_id
                        for message in messages
                        if message.membership_id
                    }
                )
            )
        ).all()
    }

    return MessageListResponse(
        items=[
            message_response(
                message,
                members.get(message.member_id),
                memberships.get(message.membership_id),
            )
            for message in messages
        ],
        total=total or 0,
        counts=counts,
    )


@router.post(
    "/communications/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_custom_message(
    data: CustomMessageCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("communications.send")),
):
    business_id = get_business_id(current_user)
    member = get_member_or_404(db, data.member_id, business_id)

    preference = db.get(MemberCommunicationPreference, member.id)

    if preference is not None and preference.opted_out:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This member has opted out of messages.",
        )

    preferred = data.channel or (
        preference.preferred_channel if preference else DEFAULT_CHANNEL
    )

    if data.channel is not None:
        choice = pick_channel(member, data.channel)

        if choice is None or choice[0] != data.channel:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "This member has no "
                    + ("email address" if data.channel == "email"
                       else "valid phone number")
                    + " on record."
                ),
            )
    else:
        choice = pick_channel(member, preferred)

        if choice is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "This member has no valid phone number or email "
                    "address on record."
                ),
            )

    channel, recipient = choice

    message = CommunicationMessage(
        business_id=business_id,
        member_id=member.id,
        kind="custom",
        channel=channel,
        recipient=recipient,
        subject=data.subject,
        body=data.body,
        status="queued",
        created_by=get_user_id(current_user),
    )
    db.add(message)
    db.flush()

    audit_message(
        db,
        message=message,
        current_user=current_user,
        action="communication.message_created",
        notes="A message was written for a member.",
    )

    db.commit()
    db.refresh(message)

    return load_message_response(db, message)


@router.post(
    "/communications/messages/{message_id}/mark-sent",
    response_model=MessageResponse,
)
def mark_message_sent(
    message_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("communications.send")),
):
    business_id = get_business_id(current_user)
    message = get_message_or_404(db, message_id, business_id)

    if message.status != "queued":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A {message.status} message cannot be marked sent.",
        )

    message.status = "sent"
    message.sent_at = datetime.now(timezone.utc)
    message.sent_by = get_user_id(current_user)

    audit_message(
        db,
        message=message,
        current_user=current_user,
        action="communication.message_sent",
        notes="A message was marked as sent.",
    )

    db.commit()
    db.refresh(message)

    return load_message_response(db, message)


@router.post(
    "/communications/messages/{message_id}/cancel",
    response_model=MessageResponse,
)
def cancel_message(
    message_id: UUID,
    data: MessageCancel | None = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("communications.send")),
):
    business_id = get_business_id(current_user)
    message = get_message_or_404(db, message_id, business_id)

    if message.status != "queued":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A {message.status} message cannot be cancelled.",
        )

    message.status = "cancelled"
    message.cancelled_at = datetime.now(timezone.utc)
    message.cancel_reason = data.reason if data else None

    audit_message(
        db,
        message=message,
        current_user=current_user,
        action="communication.message_cancelled",
        notes="A queued message was cancelled.",
        extra={"has_reason": bool(message.cancel_reason)},
    )

    db.commit()
    db.refresh(message)

    return load_message_response(db, message)
