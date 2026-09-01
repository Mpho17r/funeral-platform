from app.dependencies.roles import require_admin
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.business import Business
from app.schemas.business import BusinessCreate, BusinessResponse
from app.dependencies.auth import get_current_user


router = APIRouter(
    prefix="/businesses",
    tags=["Businesses"],
)


@router.post(
    "",
    response_model=BusinessResponse,
    status_code=201,
)
def create_business(
    business_data: BusinessCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin),
):

    existing_business = (
        db.query(Business)
        .filter(Business.slug == business_data.slug)
        .first()
    )

    if existing_business:
        raise HTTPException(
            status_code=409,
            detail="Business slug already exists",
        )

    business = Business(
        **business_data.model_dump(),
    )

    db.add(business)
    db.commit()
    db.refresh(business)

    return business


@router.get("/{business_id}", response_model=BusinessResponse)
def get_business(
    business_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if current_user["business_id"] != business_id:
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this business",
        )

    business = (
        db.query(Business)
        .filter(Business.id == business_id)
        .first()
    )

    if not business:
        raise HTTPException(
            status_code=404,
            detail="Business not found",
        )

    return business
