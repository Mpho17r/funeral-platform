from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.services import global_search

router = APIRouter(prefix="/search", tags=["Search"])


@router.get("")
def search(
    q: str = Query("", max_length=100),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Any signed-in person can search; results follow their permissions."""
    return global_search.search(
        db,
        business_id=UUID(str(current_user["business_id"])),
        user_id=UUID(str(current_user["user_id"])),
        role=current_user["role"],
        query=q,
    )
