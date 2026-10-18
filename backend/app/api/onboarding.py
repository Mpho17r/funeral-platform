from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission
from app.models.branch import Branch
from app.models.business import Business
from app.models.funeral_case import FuneralCase
from app.models.member import Member
from app.models.membership_plan import MembershipPlan
from app.models.user import User


router = APIRouter(prefix="/onboarding", tags=["Onboarding"])


@router.get("/status")
def onboarding_status(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("dashboard.view")),
):
    """What a new funeral home still has to set up. Worked out from the
    data itself, so it stays true when things are done in any order."""

    business_id = current_user["business_id"]
    business = db.get(Business, business_id)

    def count(model, *conditions):
        return (
            db.query(model)
            .filter(model.business_id == business_id, *conditions)
            .count()
        )

    has_contact = bool(
        business and (business.phone or "").strip()
    )
    has_logo = bool(business and business.logo_url)
    branches = count(Branch, Branch.is_active.is_(True))
    team = count(User, User.is_active.is_(True))
    plans = count(MembershipPlan, MembershipPlan.is_active.is_(True))
    members = count(Member, Member.archived_at.is_(None))
    cases = count(FuneralCase)

    steps = [
        {
            "key": "contact",
            "title": "Add your business phone number",
            "detail": "Shown to families in reminders and messages.",
            "path": "/settings/business",
            "done": has_contact,
            "required": True,
        },
        {
            "key": "logo",
            "title": "Upload your logo",
            "detail": "Appears on documents and the sidebar.",
            "path": "/settings/branding",
            "done": has_logo,
            "required": False,
        },
        {
            "key": "plans",
            "title": "Create your membership plans",
            "detail": "Cover levels, contributions and waiting periods.",
            "path": "/membership-plans",
            "done": plans > 0,
            "required": True,
        },
        {
            "key": "members",
            "title": "Bring in your members",
            "detail": "Import the list you already keep in a spreadsheet.",
            "path": "/settings/import",
            "done": members > 0,
            "required": True,
        },
        {
            "key": "team",
            "title": "Invite your team",
            "detail": "Give each person their own sign-in and role.",
            "path": "/settings/team",
            "done": team > 1,
            "required": False,
        },
        {
            "key": "branches",
            "title": "Add your other branches",
            "detail": "Only if you run from more than one place.",
            "path": "/branches",
            "done": branches > 1,
            "required": False,
        },
        {
            "key": "case",
            "title": "Register your first case",
            "detail": "Start arrangements for a family.",
            "path": "/cases",
            "done": cases > 0,
            "required": False,
        },
    ]

    required = [s for s in steps if s["required"]]

    return {
        "steps": steps,
        "done": sum(1 for s in steps if s["done"]),
        "total": len(steps),
        "required_complete": all(s["done"] for s in required),
    }
