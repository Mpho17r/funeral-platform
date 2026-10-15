from decimal import Decimal
from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission
from app.services.branch_service import (
    BranchError,
    resolve_branch_id,
)
from app.models.communication import (
    CommunicationMessage,
    MemberCommunicationPreference,
)
from app.models.covered_dependent import CoveredDependent
from app.models.member import Member
from app.models.membership import Membership
from app.models.membership_beneficiary import MembershipBeneficiary
from app.models.membership_contribution import MembershipContribution
from app.models.membership_payment import MembershipPayment
from app.schemas.member import (
    MemberAnonymise,
    MemberCreate,
    MemberResponse,
    MemberUpdate,
)
from app.services.audit_service import (
    build_audit_changes,
    create_audit_log,
    snapshot_fields,
)

router = APIRouter(
    prefix="/members",
    tags=["Members"],
)


def get_business_id(current_user: dict) -> UUID:
    business_id = current_user.get("business_id")

    if not business_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not associated with a business",
        )

    try:
        return UUID(str(business_id))
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid business ID",
        )


AUDITED_MEMBER_FIELDS = (
    "member_number",
    "first_name",
    "last_name",
    "id_number",
    "date_of_birth",
    "phone",
    "email",
    "address",
    "join_date",
    "status",
)

# Memberships in these states still carry cover or an obligation, so the
# member cannot be archived until they are cancelled.
RUNNING_MEMBERSHIP_STATUSES = ("active", "arrears")

ANONYMISED_FIRST_NAME = "Anonymised"
ANONYMISED_LAST_NAME = "Member"
REMOVED = "[removed]"


def actor_id(current_user: dict) -> UUID:
    return UUID(str(current_user["user_id"]))


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

    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found",
        )

    return member


def ensure_identity_number_is_free(
    db: Session,
    business_id: UUID,
    id_number: str | None,
    *,
    exclude_member_id: UUID | None = None,
) -> None:
    """One person should not be on the books twice."""

    if not id_number:
        return

    query = db.query(Member).filter(
        Member.business_id == business_id,
        Member.id_number == id_number,
        Member.archived_at.is_(None),
    )

    if exclude_member_id is not None:
        query = query.filter(Member.id != exclude_member_id)

    if query.first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A member with this ID number already exists",
        )


@router.post(
    "",
    response_model=MemberResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_member(
    member_data: MemberCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("members.create")),
):
    business_id = get_business_id(current_user)

    existing_member = (
        db.query(Member)
        .filter(
            Member.business_id == business_id,
            Member.member_number == member_data.member_number.strip(),
        )
        .first()
    )

    if existing_member:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Member number already exists",
        )

    ensure_identity_number_is_free(
        db,
        business_id,
        member_data.id_number,
    )

    try:
        branch_id = resolve_branch_id(
            db,
            business_id=business_id,
            requested=member_data.branch_id,
            acting_user_id=current_user["user_id"],
        )
    except BranchError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail=error.detail,
        )

    member = Member(
        business_id=business_id,
        branch_id=branch_id,
        member_number=member_data.member_number.strip(),
        first_name=member_data.first_name.strip(),
        last_name=member_data.last_name.strip(),
        id_number=member_data.id_number,
        date_of_birth=member_data.date_of_birth,
        phone=member_data.phone,
        email=member_data.email,
        address=member_data.address,
        join_date=member_data.join_date or date.today(),
        status=member_data.status,
    )

    db.add(member)
    db.flush()

    # Names, numbers and addresses stay out of the audit trail; it
    # records that a member was created and the non-personal facts.
    create_audit_log(
        db,
        business_id=business_id,
        user_id=actor_id(current_user),
        action="member.created",
        entity_type="member",
        entity_id=member.id,
        details={
            "member_number": member.member_number,
            "status": member.status,
            "branch_id": (
                str(member.branch_id) if member.branch_id else None
            ),
            "join_date": member.join_date.isoformat(),
        },
        notes="Member was created.",
    )

    db.commit()
    db.refresh(member)

    return member


@router.get(
    "",
    response_model=list[MemberResponse],
)
def list_members(
    branch_id: UUID | None = None,
    archived: bool = Query(
        default=False,
        description="True lists archived members instead of current ones.",
    ),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("members.view")),
):
    business_id = get_business_id(current_user)

    query = db.query(Member).filter(Member.business_id == business_id)

    if archived:
        query = query.filter(Member.archived_at.is_not(None))
    else:
        query = query.filter(Member.archived_at.is_(None))

    if branch_id is not None:
        query = query.filter(Member.branch_id == branch_id)

    return query.order_by(Member.created_at.desc()).all()


@router.get(
    "/{member_id}",
    response_model=MemberResponse,
)
def get_member(
    member_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("members.view")),
):
    business_id = get_business_id(current_user)

    # An archived member can still be opened, so records that point to
    # them (cases, claims, payments) stay readable.
    return get_member_or_404(db, member_id, business_id)


@router.patch(
    "/{member_id}",
    response_model=MemberResponse,
)
def update_member(
    member_id: UUID,
    member_data: MemberUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("members.edit")),
):
    business_id = get_business_id(current_user)

    member = get_member_or_404(db, member_id, business_id)

    if member.archived_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Restore this member before changing their details",
        )

    updates = member_data.model_dump(exclude_unset=True)

    if "member_number" in updates and updates["member_number"] is not None:
        updates["member_number"] = updates["member_number"].strip()

        duplicate = (
            db.query(Member)
            .filter(
                Member.business_id == business_id,
                Member.member_number == updates["member_number"],
                Member.id != member.id,
            )
            .first()
        )

        if duplicate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Member number already exists",
            )

    if "id_number" in updates:
        ensure_identity_number_is_free(
            db,
            business_id,
            updates["id_number"],
            exclude_member_id=member.id,
        )

    if "first_name" in updates and updates["first_name"] is not None:
        updates["first_name"] = updates["first_name"].strip()

    if "last_name" in updates and updates["last_name"] is not None:
        updates["last_name"] = updates["last_name"].strip()

    before = snapshot_fields(member, AUDITED_MEMBER_FIELDS)

    for field, value in updates.items():
        setattr(member, field, value)

    after = snapshot_fields(member, AUDITED_MEMBER_FIELDS)
    changes = build_audit_changes(before, after)

    if changes:
        create_audit_log(
            db,
            business_id=business_id,
            user_id=actor_id(current_user),
            action="member.updated",
            entity_type="member",
            entity_id=member.id,
            details={"changes": changes},
            notes="Member was updated.",
        )

    db.commit()
    db.refresh(member)

    return member


@router.delete(
    "/{member_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def archive_member(
    member_id: UUID,
    reason: str | None = Query(default=None, max_length=500),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("members.delete")),
):
    """Archive a member. Nothing is deleted: memberships, payments and
    claims stay on record and the member can be restored."""

    business_id = get_business_id(current_user)

    member = get_member_or_404(db, member_id, business_id)

    if member.archived_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Member is already archived",
        )

    running = (
        db.query(Membership)
        .filter(
            Membership.member_id == member.id,
            Membership.business_id == business_id,
            Membership.status.in_(RUNNING_MEMBERSHIP_STATUSES),
        )
        .count()
    )

    if running:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This member has a running membership. Cancel it "
                "before archiving the member."
            ),
        )

    now = datetime.now(timezone.utc)

    member.archived_at = now
    member.archived_by = actor_id(current_user)
    member.archive_reason = (reason or "").strip() or None

    # Anything still waiting to be sent to them is no longer wanted.
    cancelled = (
        db.query(CommunicationMessage)
        .filter(
            CommunicationMessage.business_id == business_id,
            CommunicationMessage.member_id == member.id,
            CommunicationMessage.status == "queued",
        )
        .update(
            {
                "status": "cancelled",
                "cancelled_at": now,
                "cancel_reason": "Member was archived",
            },
            synchronize_session=False,
        )
    )

    create_audit_log(
        db,
        business_id=business_id,
        user_id=actor_id(current_user),
        action="member.archived",
        entity_type="member",
        entity_id=member.id,
        details={
            "member_number": member.member_number,
            "reason_given": member.archive_reason is not None,
            "queued_messages_cancelled": cancelled,
        },
        notes="Member was archived.",
    )

    db.commit()

    return None


@router.post(
    "/{member_id}/restore",
    response_model=MemberResponse,
)
def restore_member(
    member_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("members.restore")),
):
    business_id = get_business_id(current_user)

    member = get_member_or_404(db, member_id, business_id)

    if member.archived_at is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Member is not archived",
        )

    if member.anonymised_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This member's personal details were permanently "
                "removed, so they cannot be restored"
            ),
        )

    ensure_identity_number_is_free(
        db,
        business_id,
        member.id_number,
        exclude_member_id=member.id,
    )

    member.archived_at = None
    member.archived_by = None
    member.archive_reason = None

    create_audit_log(
        db,
        business_id=business_id,
        user_id=actor_id(current_user),
        action="member.restored",
        entity_type="member",
        entity_id=member.id,
        details={"member_number": member.member_number},
        notes="Member was restored.",
    )

    db.commit()
    db.refresh(member)

    return member


# ============================================================
# PERSONAL DATA (POPIA)
# ============================================================

def row(instance, fields) -> dict:
    """The chosen fields of a record. Money and percentages are written
    as exact text ("250.00") rather than floating-point numbers."""

    values = {field: getattr(instance, field) for field in fields}

    return {
        field: str(value) if isinstance(value, Decimal) else value
        for field, value in values.items()
    }


@router.get("/{member_id}/personal-data")
def export_member_data(
    member_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("members.export")),
):
    """Everything held about one member, for a data access request.
    Every download is recorded in the audit trail."""

    business_id = get_business_id(current_user)

    member = get_member_or_404(db, member_id, business_id)

    memberships = (
        db.query(Membership)
        .filter(
            Membership.member_id == member.id,
            Membership.business_id == business_id,
        )
        .order_by(Membership.start_date)
        .all()
    )
    membership_ids = [membership.id for membership in memberships]

    def by_membership(model, order):
        if not membership_ids:
            return []

        return (
            db.query(model)
            .filter(
                model.business_id == business_id,
                model.membership_id.in_(membership_ids),
            )
            .order_by(order)
            .all()
        )

    dependents = by_membership(CoveredDependent, CoveredDependent.created_at)
    beneficiaries = by_membership(
        MembershipBeneficiary, MembershipBeneficiary.created_at
    )
    contributions = by_membership(
        MembershipContribution, MembershipContribution.due_date
    )
    payments = by_membership(
        MembershipPayment, MembershipPayment.payment_date
    )

    preference = (
        db.query(MemberCommunicationPreference)
        .filter(
            MemberCommunicationPreference.business_id == business_id,
            MemberCommunicationPreference.member_id == member.id,
        )
        .first()
    )

    messages = (
        db.query(CommunicationMessage)
        .filter(
            CommunicationMessage.business_id == business_id,
            CommunicationMessage.member_id == member.id,
        )
        .order_by(CommunicationMessage.created_at)
        .all()
    )

    data = {
        "generated_at": datetime.now(timezone.utc),
        "member": row(
            member,
            (
                "member_number",
                "first_name",
                "last_name",
                "id_number",
                "date_of_birth",
                "phone",
                "email",
                "address",
                "join_date",
                "status",
                "created_at",
                "archived_at",
                "anonymised_at",
            ),
        ),
        "memberships": [
            row(
                item,
                (
                    "membership_number",
                    "start_date",
                    "status",
                    "arrears_since",
                    "lapsed_at",
                    "cancelled_at",
                ),
            )
            for item in memberships
        ],
        "covered_dependents": [
            row(
                item,
                (
                    "first_name",
                    "last_name",
                    "relationship",
                    "id_number",
                    "date_of_birth",
                    "phone",
                    "status",
                    "cover_start_date",
                    "cover_end_date",
                ),
            )
            for item in dependents
        ],
        "beneficiaries": [
            row(
                item,
                (
                    "first_name",
                    "last_name",
                    "relationship",
                    "id_number",
                    "phone",
                    "email",
                    "share_percent",
                ),
            )
            for item in beneficiaries
        ],
        "contributions": [
            row(
                item,
                (
                    "contribution_period",
                    "amount_due",
                    "amount_paid",
                    "due_date",
                    "status",
                ),
            )
            for item in contributions
        ],
        "payments": [
            row(
                item,
                (
                    "amount",
                    "payment_method",
                    "reference",
                    "payment_date",
                ),
            )
            for item in payments
        ],
        "communication_preference": (
            row(
                preference,
                ("preferred_channel", "opted_out", "opted_out_at"),
            )
            if preference is not None
            else None
        ),
        "messages": [
            row(
                item,
                (
                    "kind",
                    "channel",
                    "recipient",
                    "subject",
                    "body",
                    "status",
                    "created_at",
                    "sent_at",
                ),
            )
            for item in messages
        ],
    }

    create_audit_log(
        db,
        business_id=business_id,
        user_id=actor_id(current_user),
        action="member.data_exported",
        entity_type="member",
        entity_id=member.id,
        details={
            "member_number": member.member_number,
            "memberships": len(memberships),
            "dependents": len(dependents),
            "beneficiaries": len(beneficiaries),
            "messages": len(messages),
        },
        notes="A member's personal data was downloaded.",
    )

    db.commit()

    return jsonable_encoder(data)


@router.post(
    "/{member_id}/anonymise",
    response_model=MemberResponse,
)
def anonymise_member(
    member_id: UUID,
    data: MemberAnonymise,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("members.anonymise")),
):
    """Permanently remove a former member's personal details.

    Only an archived member can be anonymised. Payments, contributions
    and claims stay (the business must keep its financial records) but
    no longer point to a named person. This cannot be undone.
    """

    business_id = get_business_id(current_user)

    member = get_member_or_404(db, member_id, business_id)

    if member.archived_at is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Archive the member before removing their details",
        )

    if member.anonymised_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This member has already been anonymised",
        )

    if data.confirm_member_number.strip() != member.member_number:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The member number does not match",
        )

    now = datetime.now(timezone.utc)

    member.first_name = ANONYMISED_FIRST_NAME
    member.last_name = ANONYMISED_LAST_NAME
    member.id_number = None
    member.date_of_birth = None
    member.phone = None
    member.email = None
    member.address = None
    member.archive_reason = None
    member.anonymised_at = now

    membership_ids = [
        item
        for (item,) in db.query(Membership.id)
        .filter(
            Membership.member_id == member.id,
            Membership.business_id == business_id,
        )
        .all()
    ]

    dependents = 0
    beneficiaries = 0

    if membership_ids:
        dependents = (
            db.query(CoveredDependent)
            .filter(
                CoveredDependent.business_id == business_id,
                CoveredDependent.membership_id.in_(membership_ids),
            )
            .update(
                {
                    "first_name": ANONYMISED_FIRST_NAME,
                    "last_name": ANONYMISED_LAST_NAME,
                    "id_number": None,
                    "date_of_birth": None,
                    "phone": None,
                },
                synchronize_session=False,
            )
        )

        beneficiaries = (
            db.query(MembershipBeneficiary)
            .filter(
                MembershipBeneficiary.business_id == business_id,
                MembershipBeneficiary.membership_id.in_(membership_ids),
            )
            .update(
                {
                    "first_name": ANONYMISED_FIRST_NAME,
                    "last_name": ANONYMISED_LAST_NAME,
                    "id_number": None,
                    "phone": None,
                    "email": None,
                    "notes": None,
                },
                synchronize_session=False,
            )
        )

    messages = (
        db.query(CommunicationMessage)
        .filter(
            CommunicationMessage.business_id == business_id,
            CommunicationMessage.member_id == member.id,
        )
        .update(
            {
                "recipient": REMOVED,
                "subject": None,
                "body": REMOVED,
                "cancel_reason": None,
            },
            synchronize_session=False,
        )
    )

    db.query(MemberCommunicationPreference).filter(
        MemberCommunicationPreference.business_id == business_id,
        MemberCommunicationPreference.member_id == member.id,
    ).update(
        {"opt_out_reason": None},
        synchronize_session=False,
    )

    create_audit_log(
        db,
        business_id=business_id,
        user_id=actor_id(current_user),
        action="member.anonymised",
        entity_type="member",
        entity_id=member.id,
        details={
            "member_number": member.member_number,
            "dependents": dependents,
            "beneficiaries": beneficiaries,
            "messages": messages,
        },
        notes="A member's personal details were permanently removed.",
    )

    db.commit()
    db.refresh(member)

    return member
