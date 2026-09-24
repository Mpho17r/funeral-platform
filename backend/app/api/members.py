from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission
from app.models.member import Member
from app.schemas.member import (
    MemberCreate,
    MemberResponse,
    MemberUpdate,
)

router = APIRouter(
    prefix="/members",
    tags=["Members"],
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


@router.post(
    "",
    response_model=MemberResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_member(
    member_data: MemberCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("members.create")),
):
    business_id = get_business_id(current_user)

    existing_member = (
        db.query(Member)
        .filter(
            Member.business_id == business_id,
            Member.member_number == member_data.member_number.strip(),
        )
        .first()
    )

    if existing_member:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Member number already exists",
        )

    member = Member(
        business_id=business_id,
        member_number=member_data.member_number.strip(),
        first_name=member_data.first_name.strip(),
        last_name=member_data.last_name.strip(),
        id_number=member_data.id_number,
        date_of_birth=member_data.date_of_birth,
        phone=member_data.phone,
        email=member_data.email,
        address=member_data.address,
        join_date=member_data.join_date or date.today(),
        status=member_data.status,
    )

    db.add(member)
    db.commit()
    db.refresh(member)

    return member


@router.get(
    "",
    response_model=list[MemberResponse],
)
def list_members(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("members.view")),
):
    business_id = get_business_id(current_user)

    return (
        db.query(Member)
        .filter(Member.business_id == business_id)
        .order_by(Member.created_at.desc())
        .all()
    )


@router.get(
    "/{member_id}",
    response_model=MemberResponse,
)
def get_member(
    member_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("members.view")),
):
    business_id = get_business_id(current_user)

    member = (
        db.query(Member)
        .filter(
            Member.id == member_id,
            Member.business_id == business_id,
        )
        .first()
    )

    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found",
        )

    return member


@router.patch(
    "/{member_id}",
    response_model=MemberResponse,
)
def update_member(
    member_id: UUID,
    member_data: MemberUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("members.edit")),
):
    business_id = get_business_id(current_user)

    member = (
        db.query(Member)
        .filter(
            Member.id == member_id,
            Member.business_id == business_id,
        )
        .first()
    )

    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found",
        )

    updates = member_data.model_dump(exclude_unset=True)

    if "member_number" in updates and updates["member_number"] is not None:
        updates["member_number"] = updates["member_number"].strip()

        duplicate = (
            db.query(Member)
            .filter(
                Member.business_id == business_id,
                Member.member_number == updates["member_number"],
                Member.id != member.id,
            )
            .first()
        )

        if duplicate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Member number already exists",
            )

    if "first_name" in updates and updates["first_name"] is not None:
        updates["first_name"] = updates["first_name"].strip()

    if "last_name" in updates and updates["last_name"] is not None:
        updates["last_name"] = updates["last_name"].strip()

    for field, value in updates.items():
        setattr(member, field, value)

    db.commit()
    db.refresh(member)

    return member


@router.delete(
    "/{member_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_member(
    member_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("members.delete")),
):
    business_id = get_business_id(current_user)

    member = (
        db.query(Member)
        .filter(
            Member.id == member_id,
            Member.business_id == business_id,
        )
        .first()
    )

    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found",
        )

    db.delete(member)
    db.commit()

    return None
