"""Branch rules.

Pure business rules with no HTTP concerns, so the same rules can later
serve portals, automation and integrations.
"""

from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.branch import Branch
from app.models.funeral_case import FuneralCase
from app.models.member import Member
from app.models.resource import Resource
from app.models.user import User


MAIN_BRANCH_NAME = "Main Branch"
MAIN_BRANCH_CODE = "MAIN"

# Cases that are still being worked on. A branch that still has any of
# these cannot be deactivated.
LIVE_CASE_STATUSES = ("open", "confirmed", "in_progress")


class BranchError(Exception):
    """A branch rule was violated."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def create_main_branch(db: Session, business_id: UUID) -> Branch:
    """Create the main branch of a new business.

    The caller is responsible for committing the transaction.
    """

    branch = Branch(
        business_id=business_id,
        name=MAIN_BRANCH_NAME,
        code=MAIN_BRANCH_CODE,
        is_main=True,
        is_active=True,
    )

    db.add(branch)
    db.flush()

    return branch


def get_main_branch(db: Session, business_id: UUID) -> Branch | None:
    return (
        db.query(Branch)
        .filter(
            Branch.business_id == business_id,
            Branch.is_main.is_(True),
        )
        .first()
    )


def get_assignable_branch(
    db: Session,
    business_id: UUID,
    branch_id: UUID,
) -> Branch:
    """A branch that a record may be placed in.

    It must belong to this business and be active. Records that
    already sit in a branch that was later deactivated keep it; this
    check only applies when a record is placed in a branch.
    """

    branch = (
        db.query(Branch)
        .filter(
            Branch.id == branch_id,
            Branch.business_id == business_id,
        )
        .first()
    )

    if branch is None:
        raise BranchError(422, "Branch not found")

    if not branch.is_active:
        raise BranchError(
            409,
            f"Branch {branch.name} is inactive and cannot receive "
            "new records",
        )

    return branch


def resolve_branch_id(
    db: Session,
    *,
    business_id: UUID,
    requested: UUID | None,
    acting_user_id: UUID | None,
) -> UUID | None:
    """The branch a new record is placed in.

    An explicit branch wins. Otherwise the acting user's own branch is
    used, and failing that the business's main branch. Returns None
    only for a business that has no branches at all.
    """

    if requested is not None:
        return get_assignable_branch(db, business_id, requested).id

    if acting_user_id is not None:
        own = (
            db.query(Branch.id)
            .join(User, User.branch_id == Branch.id)
            .filter(
                User.id == acting_user_id,
                Branch.business_id == business_id,
                Branch.is_active.is_(True),
            )
            .first()
        )

        if own is not None:
            return own[0]

    main = get_main_branch(db, business_id)

    return main.id if main is not None else None


def move_to_branch(
    db: Session,
    *,
    business_id: UUID,
    record,
    target_branch_id: UUID,
) -> UUID | None:
    """Move a case, member, resource or staff member to another branch.

    The target must be an active branch of the same business. Returns
    the branch the record came from. The caller audits and commits.
    """

    target = get_assignable_branch(db, business_id, target_branch_id)

    if record.branch_id == target.id:
        raise BranchError(
            409,
            f"Already in the {target.name} branch",
        )

    previous = record.branch_id
    record.branch_id = target.id

    return previous


def live_case_count(db: Session, branch: Branch) -> int:
    return (
        db.query(func.count(FuneralCase.id))
        .filter(
            FuneralCase.business_id == branch.business_id,
            FuneralCase.branch_id == branch.id,
            FuneralCase.is_archived.is_(False),
            FuneralCase.status.in_(LIVE_CASE_STATUSES),
        )
        .scalar()
    )


def ensure_can_deactivate(db: Session, branch: Branch) -> None:
    if not branch.is_active:
        raise BranchError(409, "Branch is already inactive")

    if branch.is_main:
        raise BranchError(
            409,
            "The main branch cannot be deactivated. Make another "
            "branch the main branch first.",
        )

    live = live_case_count(db, branch)

    if live:
        noun = "case" if live == 1 else "cases"

        raise BranchError(
            409,
            f"{live} live {noun} still belong to this branch. Move "
            "them to another branch or finish them first.",
        )


def branch_summary(db: Session, branch: Branch) -> dict:
    """Headline counts for one branch."""

    def count(model, *extra) -> int:
        return (
            db.query(func.count(model.id))
            .filter(
                model.business_id == branch.business_id,
                model.branch_id == branch.id,
                *extra,
            )
            .scalar()
        )

    return {
        "branch_id": branch.id,
        "active_staff": count(User, User.is_active.is_(True)),
        "active_resources": count(
            Resource, Resource.is_active.is_(True)
        ),
        "members": count(Member),
        "live_cases": live_case_count(db, branch),
        "total_cases": count(FuneralCase),
    }
