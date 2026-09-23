from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.roles import require_business_user, require_main_admin
from app.models.covered_dependent import CoveredDependent
from app.models.membership import Membership
from app.schemas.covered_dependent import (
    CoveredDependentCreate,
    CoveredDependentResponse,
    CoveredDependentUpdate,
)
from app.services.audit_service import create_audit_log


router = APIRouter(
    prefix="/covered-dependents",
    tags=["Covered Dependents"],
)


def get_business_id(current_user: dict) -> UUID:
    business_id = current_user.get("business_id")

    if not business_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is not associated with a business.",
        )

    try:
        return UUID(str(business_id))
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid business ID.",
        )


def get_membership(
    db: Session,
    membership_id: UUID,
    business_id: UUID,
) -> Membership:
    membership = db.scalar(
        select(Membership).where(
            Membership.id == membership_id,
            Membership.business_id == business_id,
        )
    )

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership not found.",
        )

    return membership


def get_covered_dependent(
    db: Session,
    dependent_id: UUID,
    business_id: UUID,
) -> CoveredDependent:
    dependent = db.scalar(
        select(CoveredDependent).where(
            CoveredDependent.id == dependent_id,
            CoveredDependent.business_id == business_id,
        )
    )

    if not dependent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Covered dependent not found.",
        )

    return dependent


def serialize_value(value):
    if value is None:
        return None

    if hasattr(value, "isoformat"):
        return value.isoformat()

    if isinstance(value, UUID):
        return str(value)

    return value


@router.post(
    "",
    response_model=CoveredDependentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_main_admin)],
)
def create_covered_dependent(
    payload: CoveredDependentCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    business_id = get_business_id(current_user)

    membership = get_membership(
        db,
        payload.membership_id,
        business_id,
    )

    if (
        payload.cover_end_date is not None
        and payload.cover_end_date < payload.cover_start_date
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cover end date cannot be before cover start date.",
        )

    existing = db.scalar(
        select(CoveredDependent).where(
            CoveredDependent.business_id == business_id,
            CoveredDependent.membership_id == membership.id,
            CoveredDependent.first_name == payload.first_name,
            CoveredDependent.last_name == payload.last_name,
            CoveredDependent.date_of_birth == payload.date_of_birth,
        )
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This covered dependent already exists for the membership.",
        )

    dependent = CoveredDependent(
        business_id=business_id,
        membership_id=membership.id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        relationship=payload.relationship,
        id_number=payload.id_number,
        date_of_birth=payload.date_of_birth,
        phone=payload.phone,
        status=payload.status,
        cover_start_date=payload.cover_start_date,
        cover_end_date=payload.cover_end_date,
    )

    db.add(dependent)
    db.flush()

    create_audit_log(
        db,
        business_id=business_id,
        user_id=current_user["user_id"],
        action="covered_dependent.created",
        entity_type="covered_dependent",
        entity_id=dependent.id,
        details={
            "membership_id": str(dependent.membership_id),
            "first_name": dependent.first_name,
            "last_name": dependent.last_name,
            "relationship": dependent.relationship,
            "status": dependent.status,
            "cover_start_date": dependent.cover_start_date.isoformat(),
            "cover_end_date": (
                dependent.cover_end_date.isoformat()
                if dependent.cover_end_date
                else None
            ),
        },
        notes="Covered dependent created by Main Admin.",
    )

    db.commit()
    db.refresh(dependent)

    return dependent


@router.get(
    "",
    response_model=list[CoveredDependentResponse],
    dependencies=[Depends(require_business_user)],
)
def list_covered_dependents(
    membership_id: UUID | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    business_id = get_business_id(current_user)

    query = select(CoveredDependent).where(
        CoveredDependent.business_id == business_id
    )

    if membership_id is not None:
        query = query.where(
            CoveredDependent.membership_id == membership_id
        )

    query = query.order_by(
        CoveredDependent.last_name.asc(),
        CoveredDependent.first_name.asc(),
    )

    return list(db.scalars(query).all())


@router.get(
    "/{dependent_id}",
    response_model=CoveredDependentResponse,
    dependencies=[Depends(require_business_user)],
)
def get_covered_dependent_by_id(
    dependent_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    business_id = get_business_id(current_user)

    return get_covered_dependent(
        db,
        dependent_id,
        business_id,
    )


@router.patch(
    "/{dependent_id}",
    response_model=CoveredDependentResponse,
    dependencies=[Depends(require_main_admin)],
)
def update_covered_dependent(
    dependent_id: UUID,
    payload: CoveredDependentUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    business_id = get_business_id(current_user)

    dependent = get_covered_dependent(
        db,
        dependent_id,
        business_id,
    )

    updates = payload.model_dump(
        exclude_unset=True
    )

    # Validate cover dates.
    if (
        "cover_end_date" in updates
        and updates["cover_end_date"] is not None
        and "cover_start_date" not in updates
        and updates["cover_end_date"] < dependent.cover_start_date
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cover end date cannot be before cover start date.",
        )

    proposed_start_date = updates.get(
        "cover_start_date",
        dependent.cover_start_date,
    )

    proposed_end_date = updates.get(
        "cover_end_date",
        dependent.cover_end_date,
    )

    if (
        proposed_end_date is not None
        and proposed_end_date < proposed_start_date
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cover end date cannot be before cover start date.",
        )

    # Capture values before the update.
    before = {
        field: serialize_value(getattr(dependent, field))
        for field in updates
    }

    # Apply update.
    for field, value in updates.items():
        setattr(dependent, field, value)

    dependent.updated_at = datetime.now(timezone.utc)

    db.flush()

    # Capture values after the update.
    after = {
        field: serialize_value(getattr(dependent, field))
        for field in updates
    }

    # Build the audit changes structure expected by the tests.
    changes = {}

    for field in updates:
        changes[field] = {
            "before": before[field],
            "after": after[field],
        }

    create_audit_log(
        db,
        business_id=business_id,
        user_id=current_user["user_id"],
        action="covered_dependent.updated",
        entity_type="covered_dependent",
        entity_id=dependent.id,
        details={
            "membership_id": str(dependent.membership_id),
            "changes": changes,
        },
        notes="Covered dependent updated by Main Admin.",
    )

    db.commit()
    db.refresh(dependent)

    return dependent


@router.delete(
    "/{dependent_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_main_admin)],
)
def delete_covered_dependent(
    dependent_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    business_id = get_business_id(current_user)

    dependent = get_covered_dependent(
        db,
        dependent_id,
        business_id,
    )

    create_audit_log(
        db,
        business_id=business_id,
        user_id=current_user["user_id"],
        action="covered_dependent.deleted",
        entity_type="covered_dependent",
        entity_id=dependent.id,
        details={
            "membership_id": str(dependent.membership_id),
            "first_name": dependent.first_name,
            "last_name": dependent.last_name,
            "relationship": dependent.relationship,
            "status": dependent.status,
            "cover_start_date": dependent.cover_start_date.isoformat(),
            "cover_end_date": (
                dependent.cover_end_date.isoformat()
                if dependent.cover_end_date
                else None
            ),
        },
        notes="Covered dependent deleted by Main Admin.",
    )

    db.delete(dependent)

    db.commit()

    return None