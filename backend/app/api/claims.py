from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission

from app.models.funeral_case import FuneralCase
from app.models.membership import Membership
from app.models.membership_beneficiary import MembershipBeneficiary
from app.models.membership_claim import MembershipClaim
from app.schemas.membership_claim import (
    BeneficiaryCreate,
    BeneficiaryResponse,
    BeneficiarySummaryResponse,
    BeneficiaryUpdate,
    ClaimApprove,
    ClaimCancel,
    ClaimCreate,
    ClaimPay,
    ClaimReject,
    ClaimResponse,
    ClaimUpdate,
)
from app.services.audit_service import build_audit_changes, create_audit_log
from app.services.claim_workflow import (
    HUNDRED,
    ClaimError,
    active_beneficiaries,
    allocated_percent,
    compute_allocations,
    coverage_snapshot,
    ensure_transition,
    max_payable,
    money,
    next_claim_number,
)
from app.services.coverage_decision import calculate_case_coverage
from app.services.permission_service import has_permission


router = APIRouter(
    tags=["Claims and Beneficiaries"],
)


# ============================================================
# HELPERS
# ============================================================

def get_business_id(current_user: dict) -> UUID:
    business_id = current_user.get("business_id")

    if not business_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not associated with a business",
        )

    return UUID(str(business_id))


def raise_claim_error(error: ClaimError):
    raise HTTPException(
        status_code=error.status_code,
        detail=error.detail,
    )


def get_membership_or_404(
    db: Session,
    membership_id: UUID,
    business_id: UUID,
    *,
    lock: bool = False,
) -> Membership:
    query = db.query(Membership).filter(
        Membership.id == membership_id,
        Membership.business_id == business_id,
    )

    if lock:
        query = query.with_for_update()

    membership = query.first()

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership not found",
        )

    return membership


def get_case_or_404(
    db: Session,
    case_id: UUID,
    business_id: UUID,
) -> FuneralCase:
    case = (
        db.query(FuneralCase)
        .filter(
            FuneralCase.id == case_id,
            FuneralCase.business_id == business_id,
        )
        .first()
    )

    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Funeral case not found",
        )

    return case


def get_beneficiary_or_404(
    db: Session,
    beneficiary_id: UUID,
    business_id: UUID,
) -> MembershipBeneficiary:
    beneficiary = (
        db.query(MembershipBeneficiary)
        .filter(
            MembershipBeneficiary.id == beneficiary_id,
            MembershipBeneficiary.business_id == business_id,
        )
        .first()
    )

    if beneficiary is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Beneficiary not found",
        )

    return beneficiary


def get_claim_or_404(
    db: Session,
    claim_id: UUID,
    business_id: UUID,
    *,
    lock: bool = False,
) -> MembershipClaim:
    query = db.query(MembershipClaim).filter(
        MembershipClaim.id == claim_id,
        MembershipClaim.business_id == business_id,
    )

    if lock:
        query = query.with_for_update()

    claim = query.first()

    if claim is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Claim not found",
        )

    return claim


BENEFICIARY_AUDIT_FIELDS = (
    "first_name",
    "last_name",
    "relationship",
    "phone",
    "email",
    "share_percent",
    "notes",
)


def other_allocated_percent(
    db: Session,
    *,
    business_id: UUID,
    membership_id: UUID,
    exclude_id: UUID | None = None,
) -> Decimal:
    beneficiaries = active_beneficiaries(
        db,
        business_id=business_id,
        membership_id=membership_id,
    )

    return allocated_percent(
        [b for b in beneficiaries if b.id != exclude_id]
    )


# ============================================================
# BENEFICIARIES
# ============================================================

@router.post(
    "/memberships/{membership_id}/beneficiaries",
    response_model=BeneficiaryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_beneficiary(
    membership_id: UUID,
    data: BeneficiaryCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_permission("beneficiaries.manage")
    ),
):
    business_id = get_business_id(current_user)

    # Locking the membership serializes concurrent share changes.
    get_membership_or_404(
        db, membership_id, business_id, lock=True
    )

    already = other_allocated_percent(
        db,
        business_id=business_id,
        membership_id=membership_id,
    )

    if already + data.share_percent > HUNDRED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Beneficiary shares cannot exceed 100% "
                f"({already}% already allocated)"
            ),
        )

    beneficiary = MembershipBeneficiary(
        business_id=business_id,
        membership_id=membership_id,
        first_name=data.first_name,
        last_name=data.last_name,
        relationship=data.relationship,
        id_number=data.id_number,
        phone=data.phone,
        email=data.email,
        share_percent=data.share_percent,
        notes=data.notes,
        is_active=True,
    )

    db.add(beneficiary)
    db.flush()

    create_audit_log(
        db,
        business_id=business_id,
        user_id=current_user["user_id"],
        action="beneficiary.created",
        entity_type="membership_beneficiary",
        entity_id=beneficiary.id,
        details={
            "membership_id": str(membership_id),
            "share_percent": str(beneficiary.share_percent),
        },
        notes="Beneficiary was added.",
    )

    db.commit()
    db.refresh(beneficiary)

    return beneficiary


@router.get(
    "/memberships/{membership_id}/beneficiaries",
    response_model=list[BeneficiaryResponse],
)
def list_beneficiaries(
    membership_id: UUID,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_permission("beneficiaries.view")
    ),
):
    business_id = get_business_id(current_user)

    get_membership_or_404(db, membership_id, business_id)

    query = db.query(MembershipBeneficiary).filter(
        MembershipBeneficiary.business_id == business_id,
        MembershipBeneficiary.membership_id == membership_id,
    )

    if not include_inactive:
        query = query.filter(MembershipBeneficiary.is_active.is_(True))

    return query.order_by(
        MembershipBeneficiary.created_at,
        MembershipBeneficiary.id,
    ).all()


@router.get(
    "/memberships/{membership_id}/beneficiaries/summary",
    response_model=BeneficiarySummaryResponse,
)
def beneficiary_summary(
    membership_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_permission("beneficiaries.view")
    ),
):
    business_id = get_business_id(current_user)

    get_membership_or_404(db, membership_id, business_id)

    beneficiaries = active_beneficiaries(
        db,
        business_id=business_id,
        membership_id=membership_id,
    )

    total = allocated_percent(beneficiaries)

    return BeneficiarySummaryResponse(
        membership_id=membership_id,
        active_beneficiaries=len(beneficiaries),
        allocated_percent=total,
        remaining_percent=HUNDRED - total,
        is_fully_allocated=total == HUNDRED,
    )


@router.patch(
    "/beneficiaries/{beneficiary_id}",
    response_model=BeneficiaryResponse,
)
def update_beneficiary(
    beneficiary_id: UUID,
    data: BeneficiaryUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_permission("beneficiaries.manage")
    ),
):
    business_id = get_business_id(current_user)

    beneficiary = get_beneficiary_or_404(db, beneficiary_id, business_id)

    get_membership_or_404(
        db, beneficiary.membership_id, business_id, lock=True
    )
    db.refresh(beneficiary)

    if not beneficiary.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Inactive beneficiaries cannot be changed",
        )

    updates = data.model_dump(exclude_unset=True)

    if "share_percent" in updates:
        others = other_allocated_percent(
            db,
            business_id=business_id,
            membership_id=beneficiary.membership_id,
            exclude_id=beneficiary.id,
        )

        if others + updates["share_percent"] > HUNDRED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Beneficiary shares cannot exceed 100% "
                    f"({others}% allocated to others)"
                ),
            )

    old_values = {
        field: getattr(beneficiary, field)
        for field in BENEFICIARY_AUDIT_FIELDS
    }

    for field, value in updates.items():
        setattr(beneficiary, field, value)

    new_values = {
        field: getattr(beneficiary, field)
        for field in BENEFICIARY_AUDIT_FIELDS
    }

    changes = build_audit_changes(old_values, new_values)

    if changes:
        create_audit_log(
            db,
            business_id=business_id,
            user_id=current_user["user_id"],
            action="beneficiary.updated",
            entity_type="membership_beneficiary",
            entity_id=beneficiary.id,
            details={
                "membership_id": str(beneficiary.membership_id),
                "changes": changes,
            },
            notes="Beneficiary was updated.",
        )

    db.commit()
    db.refresh(beneficiary)

    return beneficiary


@router.post(
    "/beneficiaries/{beneficiary_id}/deactivate",
    response_model=BeneficiaryResponse,
)
def deactivate_beneficiary(
    beneficiary_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_permission("beneficiaries.manage")
    ),
):
    business_id = get_business_id(current_user)

    beneficiary = get_beneficiary_or_404(db, beneficiary_id, business_id)

    get_membership_or_404(
        db, beneficiary.membership_id, business_id, lock=True
    )
    db.refresh(beneficiary)

    if not beneficiary.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Beneficiary is already inactive",
        )

    beneficiary.is_active = False

    create_audit_log(
        db,
        business_id=business_id,
        user_id=current_user["user_id"],
        action="beneficiary.deactivated",
        entity_type="membership_beneficiary",
        entity_id=beneficiary.id,
        details={
            "membership_id": str(beneficiary.membership_id),
            "share_percent": str(beneficiary.share_percent),
        },
        notes="Beneficiary was deactivated.",
    )

    db.commit()
    db.refresh(beneficiary)

    return beneficiary


# ============================================================
# CLAIMS: SUBMIT
# ============================================================

@router.post(
    "/claims",
    response_model=ClaimResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_claim(
    data: ClaimCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("claims.create")),
):
    business_id = get_business_id(current_user)

    case = get_case_or_404(db, data.case_id, business_id)

    if case.membership_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This case is not linked to a membership, so a "
                "membership claim cannot be raised"
            ),
        )

    if case.is_archived:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Claims cannot be raised on archived cases",
        )

    decision = calculate_case_coverage(db, case, business_id)

    claim = None

    for _attempt in range(5):
        candidate = MembershipClaim(
            business_id=business_id,
            claim_number=next_claim_number(db, business_id),
            membership_id=case.membership_id,
            case_id=case.id,
            covered_dependent_id=case.covered_dependent_id,
            status="submitted",
            claimed_amount=money(data.claimed_amount),
            submission_coverage=coverage_snapshot(decision),
            notes=data.notes,
            submitted_by=current_user["user_id"],
        )

        try:
            with db.begin_nested():
                db.add(candidate)
                db.flush()
            claim = candidate
            break
        except IntegrityError as error:
            message = str(error.orig)

            if "uq_membership_claims_one_live_per_case" in message:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This case already has a live claim",
                )

            # Claim-number collision: loop and take the next number.
            continue

    if claim is None:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not allocate a claim number, please retry",
        )

    create_audit_log(
        db,
        business_id=business_id,
        user_id=current_user["user_id"],
        action="claim.submitted",
        entity_type="membership_claim",
        entity_id=claim.id,
        details={
            "claim_number": claim.claim_number,
            "case_id": str(case.id),
            "membership_id": str(case.membership_id),
            "claimed_amount": str(claim.claimed_amount),
            "covered_at_submission": decision.covered,
        },
        notes="Claim was submitted.",
    )

    db.commit()
    db.refresh(claim)

    return claim


# ============================================================
# CLAIMS: READ
# ============================================================

@router.get(
    "/claims",
    response_model=list[ClaimResponse],
)
def list_claims(
    claim_status: str | None = None,
    membership_id: UUID | None = None,
    case_id: UUID | None = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("claims.view")),
):
    business_id = get_business_id(current_user)

    query = db.query(MembershipClaim).filter(
        MembershipClaim.business_id == business_id,
    )

    if claim_status is not None:
        query = query.filter(MembershipClaim.status == claim_status)

    if membership_id is not None:
        query = query.filter(
            MembershipClaim.membership_id == membership_id
        )

    if case_id is not None:
        query = query.filter(MembershipClaim.case_id == case_id)

    return query.order_by(MembershipClaim.created_at.desc()).all()


@router.get(
    "/claims/{claim_id}",
    response_model=ClaimResponse,
)
def get_claim(
    claim_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("claims.view")),
):
    business_id = get_business_id(current_user)

    return get_claim_or_404(db, claim_id, business_id)


# ============================================================
# CLAIMS: EDIT (before a decision)
# ============================================================

@router.patch(
    "/claims/{claim_id}",
    response_model=ClaimResponse,
)
def update_claim(
    claim_id: UUID,
    data: ClaimUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("claims.create")),
):
    business_id = get_business_id(current_user)

    claim = get_claim_or_404(db, claim_id, business_id, lock=True)

    if claim.status not in {"submitted", "under_review"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only claims awaiting a decision can be edited",
        )

    updates = data.model_dump(exclude_unset=True)

    old_values = {
        "claimed_amount": claim.claimed_amount,
        "notes": claim.notes,
    }

    if "claimed_amount" in updates:
        claim.claimed_amount = money(updates["claimed_amount"])

    if "notes" in updates:
        claim.notes = updates["notes"]

    new_values = {
        "claimed_amount": claim.claimed_amount,
        "notes": claim.notes,
    }

    changes = build_audit_changes(old_values, new_values)

    if changes:
        create_audit_log(
            db,
            business_id=business_id,
            user_id=current_user["user_id"],
            action="claim.updated",
            entity_type="membership_claim",
            entity_id=claim.id,
            details={
                "claim_number": claim.claim_number,
                "changes": changes,
            },
            notes="Claim was updated.",
        )

    db.commit()
    db.refresh(claim)

    return claim


# ============================================================
# CLAIMS: WORKFLOW
# ============================================================

@router.post(
    "/claims/{claim_id}/review",
    response_model=ClaimResponse,
)
def start_review(
    claim_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("claims.review")),
):
    business_id = get_business_id(current_user)

    claim = get_claim_or_404(db, claim_id, business_id, lock=True)

    try:
        ensure_transition(claim.status, "under_review")
    except ClaimError as error:
        raise_claim_error(error)

    claim.status = "under_review"

    create_audit_log(
        db,
        business_id=business_id,
        user_id=current_user["user_id"],
        action="claim.review_started",
        entity_type="membership_claim",
        entity_id=claim.id,
        details={"claim_number": claim.claim_number},
        notes="Claim review was started.",
    )

    db.commit()
    db.refresh(claim)

    return claim


@router.post(
    "/claims/{claim_id}/approve",
    response_model=ClaimResponse,
)
def approve_claim(
    claim_id: UUID,
    data: ClaimApprove,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("claims.review")),
):
    business_id = get_business_id(current_user)

    claim = get_claim_or_404(db, claim_id, business_id, lock=True)

    try:
        ensure_transition(claim.status, "approved")
    except ClaimError as error:
        raise_claim_error(error)

    case = get_case_or_404(db, claim.case_id, business_id)

    # Coverage is re-evaluated now: the membership may have changed
    # since the claim was submitted.
    decision = calculate_case_coverage(db, case, business_id)

    approved_amount = money(data.approved_amount)

    problems = []

    if not decision.covered:
        problems.append(f"coverage check failed: {decision.reason}")

    cap = max_payable(decision) if decision.covered else None

    if cap is not None and approved_amount > cap:
        problems.append(
            f"approved amount {approved_amount} exceeds the plan's "
            f"monetary limit of {cap}"
        )

    override_used = False

    if problems:
        if data.override_reason is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Claim cannot be approved: "
                    + "; ".join(problems)
                    + ". An override with a reason is required."
                ),
            )

        can_override = has_permission(
            db,
            user_id=current_user["user_id"],
            role=current_user["role"],
            permission_key="claims.override",
        )

        if not can_override:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Claim cannot be approved: "
                    + "; ".join(problems)
                    + ". You do not have permission to override."
                ),
            )

        override_used = True

    claim.status = "approved"
    claim.approved_amount = approved_amount
    claim.decision_coverage = coverage_snapshot(decision)
    claim.override_used = override_used
    claim.decision_reason = (
        data.override_reason if override_used else data.note
    )
    claim.decided_by = current_user["user_id"]
    claim.decided_at = datetime.now(timezone.utc)

    create_audit_log(
        db,
        business_id=business_id,
        user_id=current_user["user_id"],
        action="claim.approved",
        entity_type="membership_claim",
        entity_id=claim.id,
        details={
            "claim_number": claim.claim_number,
            "approved_amount": str(approved_amount),
            "override_used": override_used,
            "override_reason": (
                data.override_reason if override_used else None
            ),
            "override_problems": problems if override_used else [],
        },
        notes=(
            "Claim was approved with an override."
            if override_used
            else "Claim was approved."
        ),
    )

    db.commit()
    db.refresh(claim)

    return claim


@router.post(
    "/claims/{claim_id}/reject",
    response_model=ClaimResponse,
)
def reject_claim(
    claim_id: UUID,
    data: ClaimReject,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("claims.review")),
):
    business_id = get_business_id(current_user)

    claim = get_claim_or_404(db, claim_id, business_id, lock=True)

    try:
        ensure_transition(claim.status, "rejected")
    except ClaimError as error:
        raise_claim_error(error)

    case = get_case_or_404(db, claim.case_id, business_id)
    decision = calculate_case_coverage(db, case, business_id)

    claim.status = "rejected"
    claim.decision_coverage = coverage_snapshot(decision)
    claim.decision_reason = data.reason
    claim.decided_by = current_user["user_id"]
    claim.decided_at = datetime.now(timezone.utc)

    create_audit_log(
        db,
        business_id=business_id,
        user_id=current_user["user_id"],
        action="claim.rejected",
        entity_type="membership_claim",
        entity_id=claim.id,
        details={
            "claim_number": claim.claim_number,
            "reason": data.reason,
        },
        notes="Claim was rejected.",
    )

    db.commit()
    db.refresh(claim)

    return claim


@router.post(
    "/claims/{claim_id}/pay",
    response_model=ClaimResponse,
)
def pay_claim(
    claim_id: UUID,
    data: ClaimPay,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("claims.pay")),
):
    business_id = get_business_id(current_user)

    claim = get_claim_or_404(db, claim_id, business_id, lock=True)

    try:
        ensure_transition(claim.status, "paid")

        # Lock the membership so beneficiary shares cannot change
        # between validating them and recording the payout.
        get_membership_or_404(
            db, claim.membership_id, business_id, lock=True
        )

        beneficiaries = active_beneficiaries(
            db,
            business_id=business_id,
            membership_id=claim.membership_id,
        )

        allocations = compute_allocations(
            beneficiaries,
            claim.approved_amount,
        )
    except ClaimError as error:
        db.rollback()
        raise_claim_error(error)

    claim.status = "paid"
    claim.paid_at = datetime.now(timezone.utc)
    claim.paid_by = current_user["user_id"]
    claim.payment_reference = data.payment_reference
    claim.payout_allocations = allocations

    create_audit_log(
        db,
        business_id=business_id,
        user_id=current_user["user_id"],
        action="claim.paid",
        entity_type="membership_claim",
        entity_id=claim.id,
        details={
            "claim_number": claim.claim_number,
            "approved_amount": str(claim.approved_amount),
            "payment_reference": data.payment_reference,
            "beneficiary_count": len(allocations),
        },
        notes="Claim was marked as paid.",
    )

    db.commit()
    db.refresh(claim)

    return claim


@router.post(
    "/claims/{claim_id}/cancel",
    response_model=ClaimResponse,
)
def cancel_claim(
    claim_id: UUID,
    data: ClaimCancel,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("claims.create")),
):
    business_id = get_business_id(current_user)

    claim = get_claim_or_404(db, claim_id, business_id, lock=True)

    try:
        ensure_transition(claim.status, "cancelled")
    except ClaimError as error:
        raise_claim_error(error)

    # Withdrawing a claim that was already approved reverses a
    # decision, so it needs review authority, not just the right to
    # raise claims.
    if claim.status == "approved" and not has_permission(
        db,
        user_id=current_user["user_id"],
        role=current_user["role"],
        permission_key="claims.review",
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cancelling an approved claim requires review permission",
        )

    claim.status = "cancelled"
    claim.decision_reason = data.reason or claim.decision_reason

    create_audit_log(
        db,
        business_id=business_id,
        user_id=current_user["user_id"],
        action="claim.cancelled",
        entity_type="membership_claim",
        entity_id=claim.id,
        details={
            "claim_number": claim.claim_number,
            "reason": data.reason,
        },
        notes="Claim was cancelled.",
    )

    db.commit()
    db.refresh(claim)

    return claim
