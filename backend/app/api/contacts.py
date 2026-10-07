from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.roles import require_permission
from app.services.audit_service import build_audit_changes, create_audit_log
from app.models.case_contact import CaseContact
from app.models.funeral_case import FuneralCase
from app.schemas.case_contact import (
    CaseContactCreate,
    CaseContactUpdate,
    CaseContactResponse,
)


router = APIRouter(
    prefix="/cases",
    tags=["Case Contacts"],
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


def get_case_for_business(
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

    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Funeral case not found",
        )

    return case


@router.get(
    "/{case_id}/contacts",
    response_model=list[CaseContactResponse],
)
def get_case_contacts(
    case_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("contacts.view")),
):
    business_id = get_business_id(current_user)

    get_case_for_business(
        db=db,
        case_id=case_id,
        business_id=business_id,
    )

    contacts = (
        db.query(CaseContact)
        .filter(
            CaseContact.case_id == case_id,
            CaseContact.business_id == business_id,
        )
        .order_by(CaseContact.created_at.asc())
        .all()
    )

    return contacts


@router.post(
    "/{case_id}/contacts",
    response_model=CaseContactResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_case_contact(
    case_id: UUID,
    contact: CaseContactCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("contacts.manage")),
):
    business_id = get_business_id(current_user)

    get_case_for_business(
        db=db,
        case_id=case_id,
        business_id=business_id,
    )

    new_contact = CaseContact(
        business_id=business_id,
        case_id=case_id,
        contact_type=contact.contact_type,
        first_name=contact.first_name,
        last_name=contact.last_name,
        phone=contact.phone,
        email=contact.email,
        relationship=contact.relationship,
        organization=contact.organization,
        address=contact.address,
        notes=contact.notes,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    db.add(new_contact)
    db.flush()

    create_audit_log(
        db,
        business_id=business_id,
        user_id=current_user["user_id"],
        action="case.contact_created",
        entity_type="case_contact",
        entity_id=new_contact.id,
        details={
            "case_id": str(case_id),
            "contact_type": new_contact.contact_type,
        },
        notes="Case contact was created.",
    )

    db.commit()
    db.refresh(new_contact)

    return new_contact


@router.get(
    "/contacts/{contact_id}",
    response_model=CaseContactResponse,
)
def get_case_contact(
    contact_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("contacts.view")),
):
    business_id = get_business_id(current_user)

    contact = (
        db.query(CaseContact)
        .filter(
            CaseContact.id == contact_id,
            CaseContact.business_id == business_id,
        )
        .first()
    )

    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found",
        )

    return contact


@router.patch(
    "/contacts/{contact_id}",
    response_model=CaseContactResponse,
)
def update_case_contact(
    contact_id: UUID,
    contact_update: CaseContactUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("contacts.manage")),
):
    business_id = get_business_id(current_user)

    contact = (
        db.query(CaseContact)
        .filter(
            CaseContact.id == contact_id,
            CaseContact.business_id == business_id,
        )
        .first()
    )

    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found",
        )

    update_data = contact_update.model_dump(exclude_unset=True)

    old_values = {
        field: getattr(contact, field)
        for field in update_data
    }

    for field, value in update_data.items():
        setattr(contact, field, value)

    new_values = {
        field: getattr(contact, field)
        for field in update_data
    }

    changes = build_audit_changes(old_values, new_values)

    contact.updated_at = datetime.now(timezone.utc)

    if changes:
        create_audit_log(
            db,
            business_id=business_id,
            user_id=current_user["user_id"],
            action="case.contact_updated",
            entity_type="case_contact",
            entity_id=contact.id,
            details={
                "case_id": str(contact.case_id),
                "changes": changes,
            },
            notes="Case contact was updated.",
        )
    db.commit()
    db.refresh(contact)

    return contact


@router.delete(
    "/contacts/{contact_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_case_contact(
    contact_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("contacts.manage")),
):
    business_id = get_business_id(current_user)

    contact = (
        db.query(CaseContact)
        .filter(
            CaseContact.id == contact_id,
            CaseContact.business_id == business_id,
        )
        .first()
    )

    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found",
        )

    create_audit_log(
        db,
        business_id=business_id,
        user_id=current_user["user_id"],
        action="case.contact_deleted",
        entity_type="case_contact",
        entity_id=contact.id,
        details={
            "case_id": str(contact.case_id),
            "contact_type": contact.contact_type,
        },
        notes="Case contact was deleted.",
    )

    db.delete(contact)
    db.commit()

    return None
