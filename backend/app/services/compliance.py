"""
Licences and certificates that must stay valid.

A certificate of competence for the premises lasts two years (R363,
regulation 6); a lapsed one means the business may not lawfully prepare or
store remains. Everything here is about telling the right people early.
"""

from datetime import date, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.compliance import ComplianceItem
from app.services.notifications import notify, users_with_permission

KINDS = (
    "certificate_of_competence",
    "health_inspection",
    "vehicle_licence",
    "insurance",
    "other",
)

# Remind when this many days are left (each once), then weekly if expired.
REMINDER_DAYS = (90, 60, 30, 14, 7, 1)
SOON_DAYS = 90

KIND_LABELS = {
    "certificate_of_competence": "Certificate of competence",
    "health_inspection": "Health inspection",
    "vehicle_licence": "Vehicle licence or roadworthy",
    "insurance": "Insurance",
    "other": "Other",
}


def state(expires_on: date, today: date) -> str:
    days = (expires_on - today).days
    if days < 0:
        return "expired"
    if days <= 30:
        return "urgent"
    if days <= SOON_DAYS:
        return "soon"
    return "ok"


def serialize(item: ComplianceItem, today: date) -> dict:
    return {
        "id": str(item.id),
        "kind": item.kind,
        "kind_label": KIND_LABELS.get(item.kind, item.kind),
        "title": item.title,
        "reference": item.reference,
        "issued_on": item.issued_on.isoformat() if item.issued_on else None,
        "expires_on": item.expires_on.isoformat(),
        "days_left": (item.expires_on - today).days,
        "state": state(item.expires_on, today),
        "notes": item.notes,
        "status": item.status,
        "branch_id": str(item.branch_id) if item.branch_id else None,
    }


def active_items(db: Session, business_id: UUID) -> list[ComplianceItem]:
    return (
        db.query(ComplianceItem)
        .filter(
            ComplianceItem.business_id == business_id,
            ComplianceItem.status == "active",
        )
        .order_by(ComplianceItem.expires_on)
        .all()
    )


def _bucket(days_left: int, today: date) -> str | None:
    """Which reminder this moment falls into, or None for none yet."""
    if days_left < 0:
        year, week, _ = today.isocalendar()
        return f"expired-{year}-{week}"
    for limit in REMINDER_DAYS:
        if days_left <= limit:
            smallest = limit
    return f"d{smallest}" if days_left <= REMINDER_DAYS[0] else None


def run_for_business(
    db: Session, business_id: UUID, today: date | None = None
) -> int:
    """Send each renewal reminder once. Returns how many were sent."""
    from app.models.notification import Notification

    today = today or date.today()
    people = users_with_permission(db, business_id, "compliance.manage")
    sent = 0

    for item in active_items(db, business_id):
        days = (item.expires_on - today).days
        bucket = _bucket(days, today)
        if bucket is None:
            continue

        link = f"/compliance?item={item.id}&r={bucket}"
        if days < 0:
            title = f"EXPIRED: {item.title}"
            body = f"Expired {-days} day(s) ago ({item.expires_on})."
        else:
            title = f"Renew soon: {item.title}"
            body = f"Expires in {days} day(s) ({item.expires_on})."

        for user_id in people:
            already = (
                db.query(Notification.id)
                .filter(
                    Notification.user_id == user_id,
                    Notification.link == link,
                )
                .first()
            )
            if already:
                continue
            sent += notify(
                db,
                business_id=business_id,
                user_ids=[user_id],
                kind="compliance_alert",
                title=title,
                body=body,
                link=link,
            )

    db.commit()
    return sent
