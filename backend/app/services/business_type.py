"""What kind of business this is, and what that hides.

A business is either a **funeral** home (the whole platform) or a
**general** business (jobs, tasks, money, stock and staff). A general
business never sees the funeral parts - mortuary, remains, death
records, memberships and the like - and the server refuses them too:
the permissions that open those parts are removed for it, for everyone
including the main admin. Nothing changes for a funeral business.
"""

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.business import Business
from app.models.user import User

FUNERAL = "funeral"
GENERAL = "general"
TYPES = (FUNERAL, GENERAL)

# Permission groups (the part before the dot) that only make sense for a
# funeral home.
FUNERAL_ONLY_GROUPS = frozenset(
    {
        "families",
        "members",
        "membership_plans",
        "memberships",
        "contributions",
        "beneficiaries",
        "claims",
        "death_records",
        "paperwork",
        "mortuary",
        "remains",
        "viewings",
        "transport",
        "portal",
        "compliance",
        "arrangements",
        "collections",
        "run_sheet",
        "communications",
        # Everything that is built around a funeral case.
        "cases",
        "services",
        "payments",
        "financials",
        "documents",
        "contacts",
        "financial_documents",
        "receipts",
        "reconciliation",
        "resource_bookings",
        "imports",
        "reports",
        "finance",
    }
)

# Parts that only a general business has (a funeral home records money on
# its cases instead).
GENERAL_ONLY_GROUPS = frozenset({"income"})


def is_funeral_only(permission_key: str) -> bool:
    return permission_key.split(".", 1)[0] in FUNERAL_ONLY_GROUPS


def is_general_only(permission_key: str) -> bool:
    return permission_key.split(".", 1)[0] in GENERAL_ONLY_GROUPS


def hidden_for(kind: str, permission_key: str) -> bool:
    """Is this permission switched off for this kind of business?"""

    if kind == GENERAL:
        return is_funeral_only(permission_key)
    return is_general_only(permission_key)


def business_type_of_user(db: Session, user_id: UUID) -> str:
    kind = (
        db.query(Business.business_type)
        .join(User, User.business_id == Business.id)
        .filter(User.id == user_id)
        .scalar()
    )
    return kind or FUNERAL


def business_type_of(db: Session, business_id: UUID) -> str:
    return (
        db.query(Business.business_type)
        .filter(Business.id == business_id)
        .scalar()
        or FUNERAL
    )


# ------------------------------------------------- the general workspace
#
# Tasks belong to a case. A general business has no funeral cases, so its
# tasks live on one quiet container case that nobody ever sees as a case.

WORKSPACE_CASE_NUMBER = "WORK"


def workspace_case(db: Session, business_id: UUID):
    from app.models.funeral_case import FuneralCase

    case = (
        db.query(FuneralCase)
        .filter(
            FuneralCase.business_id == business_id,
            FuneralCase.case_number == WORKSPACE_CASE_NUMBER,
        )
        .execution_options(all_branches=True)
        .first()
    )
    if case is None:
        case = FuneralCase(
            business_id=business_id,
            case_number=WORKSPACE_CASE_NUMBER,
            deceased_full_name="General work",
            status="open",
        )
        db.add(case)
        db.flush()
    return case


def is_workspace_case(case) -> bool:
    return getattr(case, "case_number", None) == WORKSPACE_CASE_NUMBER
