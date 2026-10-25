from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.services import assistant

router = APIRouter(prefix="/assistant", tags=["Assistant"])


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=2, max_length=300)


@router.get("/questions")
def questions(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return assistant.available(db, current_user)


@router.post("/ask")
def ask(
    data: Question,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return assistant.ask(db, current_user, data.question)
