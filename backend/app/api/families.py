from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission
from app.models.case_contact import CaseContact
from app.models.funeral_case import FuneralCase


router = APIRouter(
    prefix="/families",
    tags=["Families"],
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


@router.get("")
def list_families(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("families.view")),
):
    business_id = get_business_id(current_user)

    contacts = (
        db.query(
            CaseContact,
            FuneralCase.case_number,
            FuneralCase.deceased_full_name,
        )
        .join(
            FuneralCase,
            FuneralCase.id == CaseContact.case_id,
        )
        .filter(
    CaseContact.business_id == business_id,
    CaseContact.contact_type.in_(
        ["family", "next_of_kin"]
    ),
    FuneralCase.business_id == business_id,
)
        .order_by(
            CaseContact.created_at.asc()
        )
        .all()
    )

    # ============================================================
    # GROUP CONTACTS BY FUNERAL CASE
    # ============================================================

    families = {}

    for contact, case_number, deceased_full_name in contacts:

        case_id = str(contact.case_id)

        if case_id not in families:
            families[case_id] = {
                "case_id": case_id,
                "case_number": case_number,
                "deceased_full_name": deceased_full_name,
                "member_count": 0,
                "members": [],
            }

        families[case_id]["members"].append(
            {
                "id": str(contact.id),
                "first_name": contact.first_name,
                "last_name": contact.last_name,
                "full_name": (
                    f"{contact.first_name} "
                    f"{contact.last_name}"
                ),
                "phone": contact.phone,
                "email": contact.email,
                "relationship": contact.relationship,
                "organization": contact.organization,
                "address": contact.address,
                "notes": contact.notes,
            }
        )

        families[case_id]["member_count"] += 1

    # ============================================================
    # RETURN ONE FAMILY GROUP PER CASE
    # ============================================================

    return list(families.values())
