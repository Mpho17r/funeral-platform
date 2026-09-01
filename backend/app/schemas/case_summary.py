from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.funeral_case import FuneralCaseResponse


class CaseContactSummary(BaseModel):
    total: int


class CaseTaskSummary(BaseModel):
    total: int
    pending: int
    completed: int


class CaseDocumentSummary(BaseModel):
    total: int


class CaseServiceSummary(BaseModel):
    total: int
    pending: int
    confirmed: int


class CasePaymentSummary(BaseModel):
    total: int
    amount_paid: Decimal


class CaseFinancialSummary(BaseModel):
    total: Decimal
    amount_paid: Decimal
    balance: Decimal
    credit: Decimal
    status: str


class CaseSummaryResponse(BaseModel):
    case: FuneralCaseResponse
    contacts: CaseContactSummary
    tasks: CaseTaskSummary
    documents: CaseDocumentSummary
    services: CaseServiceSummary
    payments: CasePaymentSummary
    financial: CaseFinancialSummary | None = None

    model_config = ConfigDict(from_attributes=True)