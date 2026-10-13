"""Business reports.

Read-only aggregates over data that already exists. Every query is
scoped to one business, and may be narrowed to one branch. Nothing
here changes data, so a report can never alter financial history.

Money rules used throughout:

- "Billed" is the total on case financials of cases created in the
  period.
- "Collected" is payments whose payment date is in the period.
- "Outstanding" is the balance still owed right now on live cases,
  so it has no period.
"""

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import case as sql_case
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.branch import Branch
from app.models.case_financial import CaseFinancial
from app.models.case_payment import CasePayment
from app.models.funeral_case import FuneralCase
from app.models.member import Member
from app.models.membership import Membership
from app.models.membership_claim import MembershipClaim
from app.models.membership_payment import MembershipPayment


ZERO = Decimal("0.00")

# Ages, in days since the case was created, for the outstanding
# balance buckets. The last bucket has no upper limit.
AGE_BUCKETS = (
    ("0-30", 0, 30),
    ("31-60", 31, 60),
    ("61-90", 61, 90),
    ("90+", 91, None),
)


class ReportError(Exception):
    """A report request was not valid."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


# ============================================================
# HELPERS
# ============================================================

def money(value) -> Decimal:
    if value is None:
        return ZERO

    return Decimal(value).quantize(Decimal("0.01"))


def validate_period(
    date_from: date | None,
    date_to: date | None,
) -> None:
    if date_from and date_to and date_from > date_to:
        raise ReportError(
            422, "The start date cannot be after the end date"
        )


def validate_branch(
    db: Session,
    business_id: UUID,
    branch_id: UUID | None,
) -> None:
    if branch_id is None:
        return

    exists = (
        db.query(Branch.id)
        .filter(
            Branch.id == branch_id,
            Branch.business_id == business_id,
        )
        .first()
    )

    if exists is None:
        raise ReportError(404, "Branch not found")


def start_of(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=timezone.utc)


def end_of(day: date) -> datetime:
    """The first instant after the day, for a half-open range."""

    return start_of(day + timedelta(days=1))


def created_in_period(column, date_from, date_to) -> list:
    conditions = []

    if date_from:
        conditions.append(column >= start_of(date_from))

    if date_to:
        conditions.append(column < end_of(date_to))

    return conditions


def date_in_period(column, date_from, date_to) -> list:
    conditions = []

    if date_from:
        conditions.append(column >= date_from)

    if date_to:
        conditions.append(column <= date_to)

    return conditions


def branch_names(db: Session, business_id: UUID) -> dict:
    rows = (
        db.query(Branch.id, Branch.name)
        .filter(Branch.business_id == business_id)
        .all()
    )

    return {row.id: row.name for row in rows}


def by_branch_rows(
    names: dict,
    values: dict,
    fields: tuple[str, ...],
) -> list[dict]:
    """One row per branch that has data, plus a row for records
    without a branch, ordered by branch name."""

    rows = []

    for branch_id, figures in values.items():
        rows.append(
            {
                "branch_id": branch_id,
                "branch_name": (
                    names.get(branch_id, "Unknown")
                    if branch_id
                    else "No branch"
                ),
                **{field: figures.get(field) for field in fields},
            }
        )

    rows.sort(key=lambda row: (row["branch_id"] is None, row["branch_name"]))

    return rows


# ============================================================
# CASES
# ============================================================

def cases_report(
    db: Session,
    *,
    business_id: UUID,
    date_from: date | None,
    date_to: date | None,
    branch_id: UUID | None,
) -> dict:
    """Cases opened in the period, and funerals held in it."""

    base = [
        FuneralCase.business_id == business_id,
        FuneralCase.is_archived.is_(False),
    ]

    if branch_id:
        base.append(FuneralCase.branch_id == branch_id)

    opened = base + created_in_period(
        FuneralCase.created_at, date_from, date_to
    )

    status_rows = (
        db.query(FuneralCase.status, func.count(FuneralCase.id))
        .filter(*opened)
        .group_by(FuneralCase.status)
        .all()
    )

    by_status = {status: count for status, count in status_rows}

    branch_rows = (
        db.query(FuneralCase.branch_id, func.count(FuneralCase.id))
        .filter(*opened)
        .group_by(FuneralCase.branch_id)
        .all()
    )

    names = branch_names(db, business_id)

    funerals_held = (
        db.query(func.count(FuneralCase.id))
        .filter(
            *base,
            FuneralCase.funeral_date.isnot(None),
            *date_in_period(
                FuneralCase.funeral_date, date_from, date_to
            ),
        )
        .scalar()
    )

    # Cases that came through a membership, against walk-ins.
    from_membership = (
        db.query(func.count(FuneralCase.id))
        .filter(*opened, FuneralCase.membership_id.isnot(None))
        .scalar()
    )

    total = sum(by_status.values())

    return {
        "date_from": date_from,
        "date_to": date_to,
        "branch_id": branch_id,
        "total_cases": total,
        "from_membership": from_membership,
        "walk_in": total - from_membership,
        "funerals_held": funerals_held,
        "by_status": [
            {"status": status, "count": count}
            for status, count in sorted(by_status.items())
        ],
        "by_branch": by_branch_rows(
            names,
            {
                bid: {"cases": count}
                for bid, count in branch_rows
            },
            ("cases",),
        ),
    }


# ============================================================
# FINANCIAL
# ============================================================

def age_bucket_label(days: int) -> str:
    for label, low, high in AGE_BUCKETS:
        if days >= low and (high is None or days <= high):
            return label

    return AGE_BUCKETS[-1][0]


def financial_report(
    db: Session,
    *,
    business_id: UUID,
    date_from: date | None,
    date_to: date | None,
    branch_id: UUID | None,
    today: date | None = None,
) -> dict:
    today = today or datetime.now(timezone.utc).date()

    case_filters = [
        FuneralCase.business_id == business_id,
        FuneralCase.is_archived.is_(False),
        FuneralCase.status != "cancelled",
    ]

    if branch_id:
        case_filters.append(FuneralCase.branch_id == branch_id)

    names = branch_names(db, business_id)

    # --- Billed: cases created in the period -------------------

    billed_rows = (
        db.query(
            FuneralCase.branch_id,
            func.coalesce(func.sum(CaseFinancial.total), ZERO),
        )
        .join(
            CaseFinancial,
            CaseFinancial.case_id == FuneralCase.id,
        )
        .filter(
            *case_filters,
            *created_in_period(
                FuneralCase.created_at, date_from, date_to
            ),
        )
        .group_by(FuneralCase.branch_id)
        .all()
    )

    # --- Collected: payments dated in the period ---------------

    collected_filters = [
        CasePayment.business_id == business_id,
        *date_in_period(CasePayment.payment_date, date_from, date_to),
    ]

    if branch_id:
        collected_filters.append(FuneralCase.branch_id == branch_id)

    collected_rows = (
        db.query(
            FuneralCase.branch_id,
            func.coalesce(func.sum(CasePayment.amount), ZERO),
        )
        .join(FuneralCase, FuneralCase.id == CasePayment.case_id)
        .filter(*collected_filters)
        .group_by(FuneralCase.branch_id)
        .all()
    )

    method_rows = (
        db.query(
            CasePayment.payment_method,
            func.coalesce(func.sum(CasePayment.amount), ZERO),
            func.count(CasePayment.id),
        )
        .join(FuneralCase, FuneralCase.id == CasePayment.case_id)
        .filter(*collected_filters)
        .group_by(CasePayment.payment_method)
        .order_by(CasePayment.payment_method)
        .all()
    )

    # --- Outstanding: what is owed right now -------------------

    owing = (
        db.query(
            FuneralCase.branch_id,
            FuneralCase.created_at,
            CaseFinancial.balance,
        )
        .join(
            CaseFinancial,
            CaseFinancial.case_id == FuneralCase.id,
        )
        .filter(*case_filters, CaseFinancial.balance > 0)
        .all()
    )

    outstanding_by_branch: dict = {}
    buckets = {label: [ZERO, 0] for label, _, _ in AGE_BUCKETS}

    for owing_branch, created_at, balance in owing:
        entry = outstanding_by_branch.setdefault(
            owing_branch, ZERO
        )
        outstanding_by_branch[owing_branch] = entry + balance

        age = (today - created_at.date()).days
        bucket = buckets[age_bucket_label(max(age, 0))]
        bucket[0] += balance
        bucket[1] += 1

    # --- Merge per-branch figures ------------------------------

    per_branch: dict = {}

    for bid, value in billed_rows:
        per_branch.setdefault(bid, {})["billed"] = money(value)

    for bid, value in collected_rows:
        per_branch.setdefault(bid, {})["collected"] = money(value)

    for bid, value in outstanding_by_branch.items():
        per_branch.setdefault(bid, {})["outstanding"] = money(value)

    for figures in per_branch.values():
        for field in ("billed", "collected", "outstanding"):
            figures.setdefault(field, ZERO)

    total_outstanding = sum(
        (balance for _, _, balance in owing), ZERO
    )

    return {
        "date_from": date_from,
        "date_to": date_to,
        "branch_id": branch_id,
        "billed": money(sum((v for _, v in billed_rows), ZERO)),
        "collected": money(sum((v for _, v in collected_rows), ZERO)),
        "outstanding": money(total_outstanding),
        "cases_with_balance": len(owing),
        "by_payment_method": [
            {
                "payment_method": method,
                "amount": money(amount),
                "payments": count,
            }
            for method, amount, count in method_rows
        ],
        "outstanding_by_age": [
            {
                "bucket": label,
                "amount": money(buckets[label][0]),
                "cases": buckets[label][1],
            }
            for label, _, _ in AGE_BUCKETS
        ],
        "by_branch": by_branch_rows(
            names,
            per_branch,
            ("billed", "collected", "outstanding"),
        ),
    }


# ============================================================
# MEMBERSHIP
# ============================================================

def membership_report(
    db: Session,
    *,
    business_id: UUID,
    date_from: date | None,
    date_to: date | None,
    branch_id: UUID | None,
) -> dict:
    """Members and memberships now, and money and claims in the
    period. A membership belongs to the branch of its member."""

    names = branch_names(db, business_id)

    member_filters = [Member.business_id == business_id]

    if branch_id:
        member_filters.append(Member.branch_id == branch_id)

    member_rows = (
        db.query(Member.status, func.count(Member.id))
        .filter(*member_filters)
        .group_by(Member.status)
        .all()
    )

    membership_rows = (
        db.query(Membership.status, func.count(Membership.id))
        .join(Member, Member.id == Membership.member_id)
        .filter(Membership.business_id == business_id, *member_filters[1:])
        .group_by(Membership.status)
        .all()
    )

    # --- Contributions collected in the period -----------------

    payment_filters = [
        MembershipPayment.business_id == business_id,
        *date_in_period(
            MembershipPayment.payment_date, date_from, date_to
        ),
    ]

    if branch_id:
        payment_filters.append(Member.branch_id == branch_id)

    payment_rows = (
        db.query(
            Member.branch_id,
            func.coalesce(func.sum(MembershipPayment.amount), ZERO),
        )
        .join(
            Membership,
            Membership.id == MembershipPayment.membership_id,
        )
        .join(Member, Member.id == Membership.member_id)
        .filter(*payment_filters)
        .group_by(Member.branch_id)
        .all()
    )

    # --- Claims raised in the period ---------------------------

    claim_filters = [
        MembershipClaim.business_id == business_id,
        *created_in_period(
            MembershipClaim.created_at, date_from, date_to
        ),
    ]

    if branch_id:
        claim_filters.append(FuneralCase.branch_id == branch_id)

    claim_rows = (
        db.query(
            MembershipClaim.status,
            func.count(MembershipClaim.id),
            func.coalesce(func.sum(MembershipClaim.claimed_amount), ZERO),
            func.coalesce(
                func.sum(
                    sql_case(
                        (
                            MembershipClaim.approved_amount.isnot(None),
                            MembershipClaim.approved_amount,
                        ),
                        else_=ZERO,
                    )
                ),
                ZERO,
            ),
        )
        .join(FuneralCase, FuneralCase.id == MembershipClaim.case_id)
        .filter(*claim_filters)
        .group_by(MembershipClaim.status)
        .order_by(MembershipClaim.status)
        .all()
    )

    # --- Members per branch ------------------------------------

    members_by_branch = (
        db.query(Member.branch_id, func.count(Member.id))
        .filter(*member_filters)
        .group_by(Member.branch_id)
        .all()
    )

    per_branch: dict = {}

    for bid, count in members_by_branch:
        per_branch.setdefault(bid, {})["members"] = count

    for bid, value in payment_rows:
        per_branch.setdefault(bid, {})["contributions"] = money(value)

    for figures in per_branch.values():
        figures.setdefault("members", 0)
        figures.setdefault("contributions", ZERO)

    return {
        "date_from": date_from,
        "date_to": date_to,
        "branch_id": branch_id,
        "total_members": sum(count for _, count in member_rows),
        "members_by_status": [
            {"status": status, "count": count}
            for status, count in sorted(member_rows)
        ],
        "memberships_by_status": [
            {"status": status, "count": count}
            for status, count in sorted(membership_rows)
        ],
        "contributions_collected": money(
            sum((value for _, value in payment_rows), ZERO)
        ),
        "claims_total": sum(row[1] for row in claim_rows),
        "claims_by_status": [
            {
                "status": status,
                "count": count,
                "claimed_amount": money(claimed),
                "approved_amount": money(approved),
            }
            for status, count, claimed, approved in claim_rows
        ],
        "by_branch": by_branch_rows(
            names,
            per_branch,
            ("members", "contributions"),
        ),
    }
