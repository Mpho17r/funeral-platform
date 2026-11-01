"""Record recurring items when they fall due, and warn when a monthly
budget is nearly or fully used."""

import calendar
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.expense import Expense
from app.models.income import IncomeEntry
from app.models.notification import Notification
from app.models.planning import Budget, RecurringItem
from app.models.user import User
from app.services.notifications import notify

# Never catch up more than this many missed periods in one run.
MAX_CATCH_UP = 12
WARN_AT = Decimal("0.80")


def advance(d: date, frequency: str, anchor_day: int | None = None) -> date:
    """The next date after d. Monthly keeps the original day where the
    month is long enough, so 31 Jan -> 28 Feb -> 31 Mar."""

    if frequency == "weekly":
        return d + timedelta(days=7)
    if frequency == "monthly":
        year, month = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
        day = min(anchor_day or d.day, calendar.monthrange(year, month)[1])
        return date(year, month, day)
    year = d.year + 1
    day = min(anchor_day or d.day, calendar.monthrange(year, d.month)[1])
    return date(year, d.month, day)


def record_due(db: Session, today: date | None = None) -> int:
    """Record every active item whose date has come. Returns how many
    entries were made."""

    today = today or date.today()
    made = 0
    items = (
        db.query(RecurringItem)
        .filter(RecurringItem.active.is_(True), RecurringItem.next_date <= today)
        .all()
    )
    for item in items:
        anchor = item.next_date.day
        runs = 0
        while item.next_date <= today and runs < MAX_CATCH_UP:
            if item.end_date and item.next_date > item.end_date:
                item.active = False
                break
            if item.kind == "income":
                db.add(
                    IncomeEntry(
                        business_id=item.business_id,
                        category=item.category,
                        description=f"{item.description} (recurring)"[:500],
                        amount=item.amount,
                        income_date=item.next_date,
                        created_by=item.created_by,
                    )
                )
            else:
                db.add(
                    Expense(
                        business_id=item.business_id,
                        category=item.category,
                        description=f"{item.description} (recurring)"[:500],
                        amount=item.amount,
                        expense_date=item.next_date,
                        payment_method="eft",
                        created_by=item.created_by,
                    )
                )
            made += 1
            runs += 1
            item.last_recorded_on = item.next_date
            item.next_date = advance(item.next_date, item.frequency, anchor)
        if item.end_date and item.next_date > item.end_date:
            item.active = False
    db.flush()
    return made


def month_bounds(today: date) -> tuple[date, date]:
    start = today.replace(day=1)
    end = date(today.year, today.month, calendar.monthrange(today.year, today.month)[1])
    return start, end


def budget_status(db: Session, business_id: UUID, today: date | None = None) -> list[dict]:
    """Each budgeted category: what was planned, what is spent this month
    and where that leaves it (ok, warning at 80%, over)."""

    today = today or date.today()
    start, end = month_bounds(today)
    spent = {
        c: Decimal(v or 0)
        for c, v in db.query(Expense.category, func.sum(Expense.amount))
        .filter(
            Expense.business_id == business_id,
            Expense.status == "recorded",
            Expense.expense_date >= start,
            Expense.expense_date <= end,
        )
        .group_by(Expense.category)
    }
    out = []
    for b in db.query(Budget).filter(Budget.business_id == business_id).order_by(Budget.category):
        used = spent.get(b.category, Decimal("0"))
        ratio = used / b.amount
        out.append(
            {
                "category": b.category,
                "budget": float(b.amount),
                "spent": float(used),
                "left": float(b.amount - used),
                "percent": round(float(ratio) * 100, 1),
                "state": "over" if ratio >= 1 else "warning" if ratio >= WARN_AT else "ok",
            }
        )
    return out


def budget_alerts(db: Session, today: date | None = None) -> int:
    """Tell the money people once a month per category when a budget is
    at 80% or used up."""

    today = today or date.today()
    sent = 0
    for (business_id,) in db.query(Budget.business_id).distinct().all():
        people = [
            u.id
            for u in db.query(User).filter(
                User.business_id == business_id,
                User.is_active.is_(True),
                User.role.in_(("main_admin", "manager", "finance")),
            )
        ]
        for row in budget_status(db, business_id, today):
            if row["state"] == "ok":
                continue
            link = f"/planning?budget={row['category']}&month={today:%Y-%m}&{row['state']}"
            for person in people:
                already = (
                    db.query(Notification.id)
                    .filter(
                        Notification.user_id == person,
                        Notification.kind == "budget",
                        Notification.link == link,
                    )
                    .first()
                )
                if already:
                    continue
                label = row["category"].replace("_", " ")
                sent += notify(
                    db,
                    business_id=business_id,
                    user_ids=[person],
                    kind="budget",
                    title=(
                        f"Budget used up: {label}"
                        if row["state"] == "over"
                        else f"Budget nearly used: {label}"
                    ),
                    body=f"R {row['spent']:.2f} of R {row['budget']:.2f} this month",
                    link=link,
                )
    return sent


def run(db: Session, today: date | None = None) -> str:
    made = record_due(db, today)
    sent = budget_alerts(db, today)
    db.commit()
    return f"{made} recurring entr{'y' if made == 1 else 'ies'}, {sent} budget alert(s)"
