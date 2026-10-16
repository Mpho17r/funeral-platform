from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class BenefitCoverageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    benefit_id: UUID
    name: str
    description: str | None
    benefit_type: str
    monetary_limit: Decimal | None
    quantity_limit: int | None
    is_included: bool


class WaitingPeriodResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # not_applicable, served, in_waiting or cause_pending
    status: str
    cause_category: str | None
    cover_start_date: date
    months: int
    ends_on: date | None
    message: str


class UpgradeWaitingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ends_on: date
    message: str


class CaseCoverageResponse(BaseModel):
    case_id: UUID
    coverage_date: date
    membership_id: UUID | None
    covered_dependent_id: UUID | None
    covered: bool
    reason: str
    plan_id: UUID | None
    plan_name: str | None
    # The plan whose benefits apply; differs from plan_id while an
    # upgrade waiting period is running.
    benefit_plan_id: UUID | None
    benefit_plan_name: str | None
    waiting_period: WaitingPeriodResponse | None
    upgrade_waiting: UpgradeWaitingResponse | None
    benefits: list[BenefitCoverageResponse]
