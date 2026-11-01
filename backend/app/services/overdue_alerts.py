"""Tell people when work given to them is late.

Each late task or service tells each responsible person once, the first
time it is found late. Finished work and archived work never alert.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.case_service import CaseService
from app.models.case_task import CaseTask
from app.models.notification import Notification
from app.models.sales import SalesDocument, SupplierBill
from app.models.user import User
from app.services import sales as sales_calc
from app.services.notifications import notify


def _already_told(db: Session, user_id, kind: str, link: str) -> bool:
    return (
        db.query(Notification.id)
        .filter(
            Notification.user_id == user_id,
            Notification.kind == kind,
            Notification.link == link,
        )
        .first()
        is not None
    )


def _tell(db, *, business_id, people, kind, title, body, link) -> int:
    count = 0
    for person in people:
        if _already_told(db, person, kind, link):
            continue
        count += notify(
            db,
            business_id=business_id,
            user_ids=[person],
            kind=kind,
            title=title,
            body=body,
            link=link,
        )
    return count


def run(db: Session, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    sent = 0

    tasks = (
        db.query(CaseTask)
        .filter(
            CaseTask.status != "completed",
            CaseTask.archived_at.is_(None),
            CaseTask.due_at.is_not(None),
            CaseTask.due_at < now,
        )
        .all()
    )
    for task in tasks:
        people = set(task.assignee_ids)
        if task.assigned_to:
            people.add(task.assigned_to)
        sent += _tell(
            db,
            business_id=task.business_id,
            people=people,
            kind="task_overdue",
            title="A task is overdue",
            body=task.title,
            link=f"/tasks?overdue={task.id}",
        )

    services = (
        db.query(CaseService)
        .filter(
            CaseService.status.notin_(("completed", "cancelled")),
            CaseService.archived_at.is_(None),
            CaseService.due_at.is_not(None),
            CaseService.due_at < now,
        )
        .all()
    )
    for service in services:
        sent += _tell(
            db,
            business_id=service.business_id,
            people=set(service.assignee_ids),
            kind="service_overdue",
            title="A service is overdue",
            body=service.service_name,
            link=f"/cases/{service.case_id}/services?overdue={service.id}",
        )

    sent += _money_alerts(db, now)

    db.commit()
    return sent


def _money_people(db: Session, business_id) -> list:
    return [
        u.id
        for u in db.query(User).filter(
            User.business_id == business_id,
            User.is_active.is_(True),
            User.role.in_(("main_admin", "manager", "finance")),
        )
    ]


def _money_alerts(db: Session, now: datetime) -> int:
    """Tell the people who handle money when a customer's invoice, or a
    bill the business owes, has gone past its due date."""

    today = now.date()
    sent = 0

    invoices = (
        db.query(SalesDocument)
        .filter(
            SalesDocument.document_type == "invoice",
            SalesDocument.status == "issued",
            SalesDocument.due_date.is_not(None),
            SalesDocument.due_date < today,
        )
        .all()
    )
    for inv in invoices:
        if sales_calc.paid_amount(db, inv.id) >= inv.total:
            continue
        sent += _tell(
            db,
            business_id=inv.business_id,
            people=_money_people(db, inv.business_id),
            kind="invoice_overdue",
            title="A customer invoice is overdue",
            body=f"{inv.number} was due {inv.due_date.isoformat()}",
            link=f"/sales/{inv.id}",
        )

    bills = (
        db.query(SupplierBill)
        .filter(
            SupplierBill.status == "unpaid",
            SupplierBill.due_date.is_not(None),
            SupplierBill.due_date < today,
        )
        .all()
    )
    for bill in bills:
        sent += _tell(
            db,
            business_id=bill.business_id,
            people=_money_people(db, bill.business_id),
            kind="bill_overdue",
            title="A bill is overdue",
            body=f"{bill.supplier_name}: {bill.description}",
            link=f"/bills?overdue={bill.id}",
        )
    return sent
