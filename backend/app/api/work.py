from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.roles import require_permission
from app.models.business import Business
from app.services import business_type as kinds
from app.services import work as service

router = APIRouter(prefix="/work", tags=["Work"])


@router.get("/mode")
def mode(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """What kind of business this is, so screens show the right things."""

    return {"business_type": kinds.business_type_of(db, user["business_id"])}


class TaskIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    due_at: datetime | None = None
    assignee_ids: list[UUID] = []
    let_kai_choose: bool = False


def _general(db: Session, user: dict) -> Business:
    business = db.get(Business, user["business_id"])
    if kinds.business_type_of(db, business.id) != kinds.GENERAL:
        raise HTTPException(
            409, "Funeral businesses add tasks from the case they belong to."
        )
    return business


@router.get("/people")
def people(
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("tasks.manage")),
):
    """Who is on the team, and what KAI detected each person does."""

    return service.team(db, db.get(Business, user["business_id"]))


@router.post("/tasks", status_code=201)
def new_task(
    data: TaskIn,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("tasks.manage")),
):
    business = _general(db, user)
    result = service.create_task(
        db,
        business=business,
        actor_id=user["user_id"],
        title=data.title.strip(),
        description=data.description,
        due_at=data.due_at,
        assignee_ids=data.assignee_ids,
        let_kai_choose=data.let_kai_choose,
    )
    db.commit()
    return result
