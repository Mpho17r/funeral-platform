"""
Tell the right people about the mortuary, instead of waiting for someone
to open the dashboard.

Two kinds of message:

- Problems (a body not cooled in time, a fridge too warm, a missed
  temperature check, a nearly full unit, a long stay, someone still not
  identified) go to the people who run the mortuary. A scheduled job sends
  each problem once a day until it is fixed.
- Hand-offs (remains taken in, remains released) go to the funeral
  operations team, so the next step in the funeral starts on time.
"""

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.business import Business
from app.models.notification import Notification
from app.services.mortuary_overview import SAST, now_utc, overview
from app.services.notifications import notify, users_with_permission

MORTUARY_TEAM_PERMISSION = "mortuary.manage"
OPERATIONS_TEAM_PERMISSION = "services.manage"

PROBLEM_TITLES = {
    "cooling_overdue": "Not cooled in time",
    "temperature": "Cold place too warm",
    "reading_overdue": "Temperature check missed",
    "capacity": "Cold place filling up",
    "long_stay": "Long stay in the mortuary",
    "not_identified": "Not yet identified",
    "cleaning_overdue": "Cleaning record missing",
}


def _today_start_utc(now: datetime) -> datetime:
    local = now.astimezone(SAST)
    start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.astimezone(now.tzinfo)


def _already_sent(
    db: Session,
    user_id,
    title: str,
    body: str | None,
    since: datetime,
    same_start: str | None = None,
) -> bool:
    query = db.query(Notification.id).filter(
        Notification.user_id == user_id,
        Notification.kind == "mortuary_alert",
        Notification.title == title,
        Notification.created_at >= since,
    )
    if same_start is not None:
        # Same subject, whatever the details (such as the exact reading).
        query = query.filter(Notification.body.like(f"{same_start}%"))
    elif body is not None:
        query = query.filter(Notification.body == body)
    return query.first() is not None


def send_problem(
    db: Session,
    *,
    business_id: UUID,
    title: str,
    body: str | None,
    link: str,
    since: datetime,
    same_start: str | None = None,
) -> int:
    """Notify the mortuary team once per `since` window."""
    sent = 0
    for user_id in users_with_permission(
        db, business_id, MORTUARY_TEAM_PERMISSION
    ):
        if _already_sent(db, user_id, title, body, since, same_start):
            continue
        sent += notify(
            db,
            business_id=business_id,
            user_ids=[user_id],
            kind="mortuary_alert",
            title=title,
            body=body,
            link=link,
        )
    return sent


def run_for_business(
    db: Session, business_id: UUID, now: datetime | None = None
) -> int:
    """Send today's mortuary problems for one business. Returns how many."""
    now = now or now_utc()
    since = _today_start_utc(now)
    data = overview(db, business_id=business_id, now=now)

    sent = 0
    for item in data["attention"]:
        title = PROBLEM_TITLES.get(item["reason"], "Mortuary needs attention")
        if item.get("case_id"):
            who = f"{item['name']} ({item['tag_number']})"
            body = f"{who}: {item['message']}"
            link = f"/cases/{item['case_id']}"
        else:
            body = item["message"]
            link = "/mortuary"
        sent += send_problem(
            db,
            business_id=business_id,
            title=title,
            body=body,
            link=link,
            since=since,
        )
    db.commit()

    # Licence and certificate renewals ride on the same scheduled job.
    from app.services import compliance

    sent += compliance.run_for_business(db, business_id)
    return sent


def run_all(db: Session) -> dict:
    """Every business. One failing business never stops the others."""
    results = {}
    for (business_id,) in db.query(Business.id).all():
        try:
            results[str(business_id)] = run_for_business(db, business_id)
        except Exception:  # noqa: BLE001 - reported as -1, others continue
            db.rollback()
            results[str(business_id)] = -1
    return results


def temperature_breach(
    db: Session, *, business_id: UUID, location, temperature_c
) -> int:
    """Right away, when a reading is above the safe limit."""
    from app.services.mortuary_overview import MAX_SAFE_TEMPERATURE

    if temperature_c <= MAX_SAFE_TEMPERATURE:
        return 0
    return send_problem(
        db,
        business_id=business_id,
        title=PROBLEM_TITLES["temperature"],
        body=f"{location.name} read {temperature_c}°C "
        f"(above {MAX_SAFE_TEMPERATURE}°C)",
        link="/mortuary",
        # A bad reading is worth repeating if it persists, so only an
        # hour of silence between messages.
        since=now_utc() - timedelta(hours=1),
        same_start=f"{location.name} read",
    )


def tell_operations(
    db: Session,
    *,
    business_id: UUID,
    title: str,
    body: str | None,
    link: str,
    actor_id=None,
) -> int:
    """Hand-off to the funeral operations team."""
    return notify(
        db,
        business_id=business_id,
        user_ids=users_with_permission(
            db, business_id, OPERATIONS_TEAM_PERMISSION
        ),
        kind="mortuary_update",
        title=title,
        body=body,
        link=link,
        actor_id=actor_id,
    )
