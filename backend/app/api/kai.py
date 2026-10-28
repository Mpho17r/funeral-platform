from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.services import kai

router = APIRouter(prefix="/kai", tags=["KAI"])


class Say(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=500)


@router.get("/hello")
def hello(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return kai.hello(db, current_user)


@router.post("/message")
def message(
    data: Say,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return kai.message(db, current_user, data.text)


@router.get("/history")
def history(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return kai.history(db, current_user)


@router.delete("/history", status_code=204)
def clear_history(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    kai.clear_history(db, current_user)


@router.post("/actions/{action_id}/confirm")
def confirm(
    action_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return kai.confirm_action(db, current_user, action_id)


@router.post("/actions/{action_id}/cancel")
def cancel(
    action_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return kai.cancel_action(db, current_user, action_id)
