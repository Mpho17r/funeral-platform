from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class ReportPeriod(BaseModel):
    date_from: date | None
    date_to: date | None
    branch_id: UUID | None


class StatusCount(BaseModel):
    status: str
    count: int


class CasesByBranch(BaseModel):
    branch_id: UUID | None
    branch_name: str
    cases: int


class CasesReport(ReportPeriod):
    total_cases: int
    from_membership: int
    walk_in: int
    funerals_held: int
    by_status: list[StatusCount]
    by_branch: list[CasesByBranch]


class PaymentMethodTotal(BaseModel):
    payment_method: str
    amount: Decimal
    payments: int


class AgeBucket(BaseModel):
    bucket: str
    amount: Decimal
    cases: int


class FinancialByBranch(BaseModel):
    branch_id: UUID | None
    branch_name: str
    billed: Decimal
    collected: Decimal
    outstanding: Decimal


class FinancialReport(ReportPeriod):
    billed: Decimal
    collected: Decimal
    outstanding: Decimal
    cases_with_balance: int
    by_payment_method: list[PaymentMethodTotal]
    outstanding_by_age: list[AgeBucket]
    by_branch: list[FinancialByBranch]


class ClaimStatusTotal(BaseModel):
    status: str
    count: int
    claimed_amount: Decimal
    approved_amount: Decimal


class MembershipByBranch(BaseModel):
    branch_id: UUID | None
    branch_name: str
    members: int
    contributions: Decimal


class MembershipReport(ReportPeriod):
    total_members: int
    members_by_status: list[StatusCount]
    memberships_by_status: list[StatusCount]
    contributions_collected: Decimal
    claims_total: int
    claims_by_status: list[ClaimStatusTotal]
    by_branch: list[MembershipByBranch]
