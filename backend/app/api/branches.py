from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission

from app.models.branch import Branch
from app.schemas.branch import (
    BranchCreate,
    BranchResponse,
    BranchSummaryResponse,
    BranchUpdate,
)
from app.services.audit_service import (
    build_audit_changes,
    create_audit_log,
    snapshot_fields,
)
from app.services.branch_service import (
    BranchError,
    branch_summary,
    ensure_can_deactivate,
    get_main_branch,
)


router = APIRouter(
    prefix="/branches",
    tags=["Branches"],
)


AUDITED_BRANCH_FIELDS = (
    "name",
    "code",
    "phone",
    "email",
    "address",
    "notes",
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


def get_user_id(current_user: dict) -> UUID:
    return UUID(str(current_user["user_id"]))


def raise_branch_error(db: Session, error: BranchError):
    db.rollback()

    raise HTTPException(
        status_code=error.status_code,
        detail=error.detail,
    )


def get_branch_or_404(
    db: Session,
    branch_id: UUID,
    business_id: UUID,
    *,
    lock: bool = False,
) -> Branch:
    query = db.query(Branch).filter(
        Branch.id == branch_id,
        Branch.business_id == business_id,
    )

    if lock:
        query = query.with_for_update()

    branch = query.first()

    if branch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Branch not found",
        )

    return branch


def lock_business_branches(db: Session, business_id: UUID) -> None:
    """Lock every branch of the business, always in the same order,
    so two changes to the main branch cannot deadlock."""

    (
        db.query(Branch.id)
        .filter(Branch.business_id == business_id)
        .order_by(Branch.id)
        .with_for_update()
        .all()
    )


def duplicate_detail(error: IntegrityError) -> str:
    message = str(error.orig)

    if "uq_branches_business_code" in message:
        return "A branch with that code already exists"

    if "uq_branches_business_name" in message:
        return "A branch with that name already exists"

    return "That branch conflicts with an existing branch"


def audit_branch(
    db: Session,
    *,
    branch: Branch,
    current_user: dict,
    action: str,
    notes: str,
    extra: dict | None = None,
) -> None:
    details = {
        "name": branch.name,
        "code": branch.code,
    }

    if extra:
        details.update(extra)

    create_audit_log(
        db,
        business_id=branch.business_id,
        user_id=get_user_id(current_user),
        action=action,
        entity_type="branch",
        entity_id=branch.id,
        details=details,
        notes=notes,
    )


# ============================================================
# CREATE
# ============================================================

@router.post(
    "",
    response_model=BranchResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_branch(
    data: BranchCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("branches.manage")),
):
    business_id = get_business_id(current_user)

    # A business always has a main branch. Should it somehow have
    # none, the first branch created becomes it.
    becomes_main = get_main_branch(db, business_id) is None

    branch = Branch(
        business_id=business_id,
        name=data.name,
        code=data.code,
        phone=data.phone,
        email=data.email,
        address=data.address,
        notes=data.notes,
        is_main=becomes_main,
        is_active=True,
    )

    db.add(branch)

    try:
        db.flush()
    except IntegrityError as error:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=duplicate_detail(error),
        )

    audit_branch(
        db,
        branch=branch,
        current_user=current_user,
        action="branch.created",
        notes="Branch was created.",
        extra={"is_main": branch.is_main},
    )

    db.commit()
    db.refresh(branch)

    return branch


# ============================================================
# READ
# ============================================================

@router.get(
    "",
    response_model=list[BranchResponse],
)
def list_branches(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("branches.view")),
):
    business_id = get_business_id(current_user)

    query = db.query(Branch).filter(Branch.business_id == business_id)

    if not include_inactive:
        query = query.filter(Branch.is_active.is_(True))

    return query.order_by(Branch.is_main.desc(), Branch.name).all()


@router.get(
    "/{branch_id}",
    response_model=BranchResponse,
)
def get_branch(
    branch_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("branches.view")),
):
    return get_branch_or_404(
        db, branch_id, get_business_id(current_user)
    )


@router.get(
    "/{branch_id}/summary",
    response_model=BranchSummaryResponse,
)
def get_branch_summary(
    branch_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("branches.view")),
):
    branch = get_branch_or_404(
        db, branch_id, get_business_id(current_user)
    )

    return branch_summary(db, branch)


# ============================================================
# UPDATE
# ============================================================

@router.patch(
    "/{branch_id}",
    response_model=BranchResponse,
)
def update_branch(
    branch_id: UUID,
    data: BranchUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("branches.manage")),
):
    business_id = get_business_id(current_user)

    branch = get_branch_or_404(db, branch_id, business_id, lock=True)

    updates = data.model_dump(exclude_unset=True)

    # Name and code are required, so null is not a change.
    for required in ("name", "code"):
        if required in updates and updates[required] is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"{required} cannot be null",
            )

    old_values = snapshot_fields(branch, AUDITED_BRANCH_FIELDS)

    for field, value in updates.items():
        setattr(branch, field, value)

    changes = build_audit_changes(
        old_values,
        snapshot_fields(branch, AUDITED_BRANCH_FIELDS),
    )

    if changes:
        audit_branch(
            db,
            branch=branch,
            current_user=current_user,
            action="branch.updated",
            notes="Branch was updated.",
            extra={"changes": changes},
        )

    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=duplicate_detail(error),
        )

    db.refresh(branch)

    return branch


# ============================================================
# ACTIVATION AND MAIN BRANCH
# ============================================================

@router.post(
    "/{branch_id}/deactivate",
    response_model=BranchResponse,
)
def deactivate_branch(
    branch_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("branches.manage")),
):
    business_id = get_business_id(current_user)

    lock_business_branches(db, business_id)

    branch = get_branch_or_404(db, branch_id, business_id)

    try:
        ensure_can_deactivate(db, branch)
    except BranchError as error:
        raise_branch_error(db, error)

    branch.is_active = False

    audit_branch(
        db,
        branch=branch,
        current_user=current_user,
        action="branch.deactivated",
        notes="Branch was deactivated.",
    )

    db.commit()
    db.refresh(branch)

    return branch


@router.post(
    "/{branch_id}/reactivate",
    response_model=BranchResponse,
)
def reactivate_branch(
    branch_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("branches.manage")),
):
    business_id = get_business_id(current_user)

    branch = get_branch_or_404(db, branch_id, business_id, lock=True)

    if branch.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Branch is already active",
        )

    branch.is_active = True

    audit_branch(
        db,
        branch=branch,
        current_user=current_user,
        action="branch.reactivated",
        notes="Branch was reactivated.",
    )

    db.commit()
    db.refresh(branch)

    return branch


@router.post(
    "/{branch_id}/make-main",
    response_model=BranchResponse,
)
def make_main_branch(
    branch_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("branches.manage")),
):
    business_id = get_business_id(current_user)

    lock_business_branches(db, business_id)

    branch = get_branch_or_404(db, branch_id, business_id)

    if branch.is_main:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This is already the main branch",
        )

    if not branch.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An inactive branch cannot be the main branch",
        )

    previous = get_main_branch(db, business_id)

    if previous is not None:
        # Clear the old main first: only one main branch may exist
        # at any moment.
        previous.is_main = False
        db.flush()

    branch.is_main = True
    db.flush()

    audit_branch(
        db,
        branch=branch,
        current_user=current_user,
        action="branch.made_main",
        notes="Branch was made the main branch.",
        extra={
            "previous_main_branch_id": (
                str(previous.id) if previous is not None else None
            ),
        },
    )

    db.commit()
    db.refresh(branch)

    return branch
