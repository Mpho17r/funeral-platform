from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission
from app.models.case_contact import CaseContact
from app.models.funeral_case import FuneralCase
from app.schemas.case_contact import WorkspaceContactResponse


router = APIRouter(
    prefix="/contacts",
    tags=["Contact Workspace"],
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


@router.get(
    "",
    response_model=list[WorkspaceContactResponse],
)
def get_workspace_contacts(
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_permission("contacts.view")
    ),
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
            FuneralCase.business_id == business_id,
        )
        .order_by(
            CaseContact.created_at.desc()
        )
        .all()
    )

    return [
        WorkspaceContactResponse(
            id=contact.id,
            business_id=contact.business_id,
            case_id=contact.case_id,
            case_number=case_number,
            deceased_full_name=deceased_full_name,
            contact_type=contact.contact_type,
            first_name=contact.first_name,
            last_name=contact.last_name,
            phone=contact.phone,
            email=contact.email,
            relationship=contact.relationship,
            organization=contact.organization,
            address=contact.address,
            notes=contact.notes,
            created_at=contact.created_at,
            updated_at=contact.updated_at,
        )
        for contact, case_number, deceased_full_name in contacts
    ]
