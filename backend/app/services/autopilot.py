"""KAI Autopilot - KAI as the platform manager, only when allowed.

The main admin switches it on and picks how far it may go:

* suggest - KAI works out what should happen and waits for a person to
  approve each item.
* auto    - KAI does it and logs every step, each with an undo.

What it may do (each can be switched off):
* create the tasks a case still needs (death record, paperwork, vehicle,
  drivers, payment follow-up, closing a finished case)
* give unassigned tasks and services to the best person
* tell managers when work is late

What it can never do: delete anything, change money, message a family,
change a case's status, or change anyone's access. Everything it does is
an ordinary task or assignment that people can edit like any other, and
is written to the audit log as KAI.

Choosing who: only active people who may see that kind of work, who are
not already at the open-work limit. Lowest workload first; people checked
in today, on the case's branch, and in the right work area come first.
Main admins are only used when nobody else qualifies.
"""

from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.branch import Branch  # noqa: F401  (keeps metadata complete)
from app.models.business import Business
from app.models.case_financial import CaseFinancial
from app.models.case_service import CaseService, CaseServiceAssignee
from app.models.case_task import CaseTask, CaseTaskAssignee
from app.models.death_record import CasePaperworkItem, DeathRecord
from app.models.funeral_case import FuneralCase
from app.models.kai import KaiAutopilotItem
from app.models.mortuary import RemainsRecord
from app.models.notification import Notification
from app.models.resource import Resource, ResourceBooking
from app.models.staff_attendance_session import StaffAttendanceSession
from app.models.transport import TransportJob
from app.models.user import User
from app.services.audit_service import create_audit_log
from app.services.business_type import GENERAL, business_type_of
from app.services.notifications import notify
from app.services.permission_service import has_permission
from app.services.staff_roles import category_for_text, suitability

SA = timezone(timedelta(hours=2))
LIVE = ("open", "confirmed", "in_progress")
OPEN_TASK = ("pending", "in_progress")
OPEN_SERVICE = ("pending", "confirmed", "in_progress")
MAX_PER_RUN = 25
MODES = ("off", "suggest", "auto")

MORTUARY_WORDS = ("embalm", "mortuary", "cold", "prepar", "dress", "viewing")
OPS_WORDS = (
    "hearse", "transport", "vehicle", "car", "coffin", "casket", "flower",
    "tent", "chair", "cater", "venue", "grave", "cemetery", "burial", "tombstone",
)


class AutopilotError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _today() -> date:
    return datetime.now(SA).date()


# ------------------------------------------------------------ who is free


def _area_for_text(text: str) -> str:
    lowered = text.lower()
    if any(w in lowered for w in MORTUARY_WORDS):
        return "mortuary"
    if any(w in lowered for w in OPS_WORDS):
        return "operations"
    return "general"


def workload(db: Session, business_id: UUID) -> dict[UUID, int]:
    """Open tasks and services each person is responsible for."""

    counts: dict[UUID, int] = {}
    task_rows = (
        db.query(CaseTaskAssignee.user_id, func.count())
        .join(CaseTask, CaseTask.id == CaseTaskAssignee.task_id)
        .filter(
            CaseTask.business_id == business_id,
            CaseTask.status.in_(OPEN_TASK),
            CaseTask.archived_at.is_(None),
        )
        .group_by(CaseTaskAssignee.user_id)
        .all()
    )
    service_rows = (
        db.query(CaseServiceAssignee.user_id, func.count())
        .join(CaseService, CaseService.id == CaseServiceAssignee.service_id)
        .filter(
            CaseService.business_id == business_id,
            CaseService.status.in_(OPEN_SERVICE),
            CaseService.archived_at.is_(None),
        )
        .group_by(CaseServiceAssignee.user_id)
        .all()
    )
    for user_id, n in list(task_rows) + list(service_rows):
        counts[user_id] = counts.get(user_id, 0) + n
    return counts


def present_today(db: Session, business_id: UUID) -> set[UUID]:
    rows = (
        db.query(StaffAttendanceSession.user_id)
        .filter(
            StaffAttendanceSession.business_id == business_id,
            StaffAttendanceSession.checked_out_at.is_(None),
        )
        .all()
    )
    return {r[0] for r in rows}


def pick_person(
    db: Session,
    business: Business,
    *,
    permission: str,
    branch_id: UUID | None,
    area: str,
    loads: dict[UUID, int] | None = None,
    present: set[UUID] | None = None,
    exclude: set[UUID] | None = None,
    text: str | None = None,
) -> User | None:
    """The best person for a piece of work, or None when nobody fits."""

    loads = loads if loads is not None else workload(db, business.id)
    present = present if present is not None else present_today(db, business.id)
    exclude = exclude or set()
    cap = business.autopilot_max_open or 8
    # First detect what the work needs, then who does that job.
    wanted = category_for_text(text) if text else "general"

    best: tuple[int, User] | None = None
    fallback: tuple[int, User] | None = None
    for person in db.query(User).filter(
        User.business_id == business.id, User.is_active.is_(True)
    ):
        if person.id in exclude:
            continue
        if not has_permission(
            db, user_id=person.id, role=person.role, permission_key=permission
        ):
            continue
        load = loads.get(person.id, 0)
        if load >= cap:
            continue
        score = load * 10
        if person.id in present:
            score -= 15
        if branch_id is not None and person.branch_id == branch_id:
            score -= 8
        if area != "general" and person.role == area:
            score -= 20
        score -= 30 * suitability(person.job_title, person.role, wanted)
        if person.role == "main_admin":
            if fallback is None or score < fallback[0]:
                fallback = (score, person)
            continue
        if best is None or score < best[0]:
            best = (score, person)
    chosen = best or fallback
    return chosen[1] if chosen else None


# ------------------------------------------------------------ proposals


def _exists(db: Session, business_id: UUID, key: str) -> bool:
    """Already proposed, done or dismissed: never propose it twice."""

    return (
        db.query(KaiAutopilotItem.id)
        .filter(
            KaiAutopilotItem.business_id == business_id,
            KaiAutopilotItem.dedupe_key == key,
            KaiAutopilotItem.status.in_(("pending", "applied", "approved", "dismissed", "undone")),
        )
        .first()
        is not None
    )


def _task_key_taken(db: Session, case_id: UUID, key: str) -> bool:
    return (
        db.query(CaseTask.id)
        .filter(CaseTask.case_id == case_id, CaseTask.auto_key == key)
        .first()
        is not None
    )


def _case_rules(db: Session, case: FuneralCase) -> list[dict]:
    """What this case still needs, as task proposals."""

    today = _today()
    wants: list[dict] = []
    base = f"{case.deceased_full_name} ({case.case_number})"
    funeral = case.funeral_date

    def want(key, title, why, area="general", due=None, desc=None):
        wants.append({"key": key, "title": title, "why": why, "area": area,
                      "due": due, "desc": desc, "case": base})

    created = case.created_at.astimezone(SA).date() if case.created_at else today
    if case.status in LIVE and not case.is_archived:
        if (today - created).days >= 1:
            has_record = (
                db.query(DeathRecord.id).filter(DeathRecord.case_id == case.id).first()
            )
            if has_record is None:
                want("death_record", "Capture the death record",
                     "There is no death record on this case yet.", "general",
                     today + timedelta(days=2))
            if funeral is None:
                want("funeral_date", "Agree and set the funeral date",
                     "No funeral date has been set.", "general",
                     today + timedelta(days=2))

        for item in (
            db.query(CasePaperworkItem)
            .filter(CasePaperworkItem.case_id == case.id, CasePaperworkItem.status == "pending")
            .all()
        ):
            kind = item.item_type.replace("_", " ")
            due = today + timedelta(days=3)
            if funeral is not None:
                due = min(due, funeral - timedelta(days=1)) if funeral > today else today
            want(f"paperwork:{item.item_type}", f"Obtain paperwork: {kind}",
                 f"{kind.capitalize()} has not been obtained yet.", "general", due)

        if funeral is not None and today <= funeral <= today + timedelta(days=14):
            booked = (
                db.query(ResourceBooking.id)
                .join(Resource, Resource.id == ResourceBooking.resource_id)
                .filter(
                    ResourceBooking.case_id == case.id,
                    ResourceBooking.status == "booked",
                    Resource.resource_type == "vehicle",
                )
                .first()
            )
            if booked is None:
                want("vehicle", "Book a vehicle for the funeral",
                     "The funeral is within 14 days and no vehicle is booked.",
                     "operations", max(today, funeral - timedelta(days=3)))
            if funeral <= today + timedelta(days=7):
                open_jobs = (
                    db.query(func.count(TransportJob.id))
                    .filter(TransportJob.case_id == case.id, TransportJob.status == "open")
                    .scalar()
                )
                if open_jobs:
                    want("drivers", "Find drivers for the family cars",
                         f"{open_jobs} family car job(s) have no driver and the funeral is within a week.",
                         "operations", max(today, funeral - timedelta(days=2)))

    owed = (
        db.query(CaseFinancial.balance).filter(CaseFinancial.case_id == case.id).scalar()
    )
    if (
        owed and owed > 0 and funeral is not None and funeral < today
        and case.status in ("in_progress", "completed") and not case.is_archived
    ):
        want("payment", "Follow up the outstanding payment",
             f"The funeral is over and R{owed:.2f} is still owed.", "finance",
             today + timedelta(days=2))

    if case.status == "completed" and not case.is_archived and not (owed and owed > 0):
        open_services = (
            db.query(func.count(CaseService.id))
            .filter(CaseService.case_id == case.id, CaseService.status.in_(OPEN_SERVICE))
            .scalar()
        )
        if not open_services:
            want("close_case", "Close this case",
                 "The funeral is complete, every service is done and nothing is owed.",
                 "general", today + timedelta(days=2))
    return wants


def plan(db: Session, business: Business) -> list[dict]:
    """Everything KAI would like to do right now, not yet de-duplicated
    against what it has already done."""

    out: list[dict] = []
    loads = workload(db, business.id)
    present = present_today(db, business.id)
    taken: dict[UUID, int] = {}  # work KAI is giving out in this plan

    def load_now():
        merged = dict(loads)
        for uid, n in taken.items():
            merged[uid] = merged.get(uid, 0) + n
        return merged

    general = business_type_of(db, business.id) == GENERAL
    if business.autopilot_create_tasks and not general:
        cases = (
            db.query(FuneralCase)
            .filter(FuneralCase.business_id == business.id, FuneralCase.is_archived.is_(False))
            .all()
        )
        for case in cases:
            for w in _case_rules(db, case):
                key = f"task:{case.id}:{w['key']}"
                if _task_key_taken(db, case.id, w["key"]):
                    continue
                person = None
                if business.autopilot_assign:
                    person = pick_person(
                        db, business, permission="tasks.view", branch_id=case.branch_id,
                        area=w["area"], loads=load_now(), present=present,
                        text=w["title"],
                    )
                    if person:
                        taken[person.id] = taken.get(person.id, 0) + 1
                out.append({
                    "kind": "create_task", "key": key, "case_id": case.id,
                    "summary": f"Create the task \"{w['title']}\" on {w['case']}"
                    + (f" and give it to {person.full_name}" if person else ""),
                    "reason": w["why"],
                    "params": {
                        "case_id": str(case.id), "auto_key": w["key"], "title": w["title"],
                        "description": w["why"],
                        "due": w["due"].isoformat() if w["due"] else None,
                        "assignee_id": str(person.id) if person else None,
                        "assignee_name": person.full_name if person else None,
                    },
                })

    if business.autopilot_assign:
        for task in (
            db.query(CaseTask)
            .filter(
                CaseTask.business_id == business.id,
                CaseTask.status.in_(OPEN_TASK),
                CaseTask.archived_at.is_(None),
            )
            .all()
        ):
            if task.assignee_ids or task.assigned_to:
                continue
            case = db.get(FuneralCase, task.case_id)
            if case is None or case.is_archived:
                continue
            person = pick_person(
                db, business, permission="tasks.view", branch_id=case.branch_id,
                area=_area_for_text(task.title), loads=load_now(), present=present,
                text=f"{task.title} {task.description or ''}",
            )
            if person is None:
                continue
            taken[person.id] = taken.get(person.id, 0) + 1
            out.append({
                "kind": "assign_task", "key": f"assign_task:{task.id}", "case_id": case.id,
                "summary": f"Give the task \"{task.title}\" ({case.deceased_full_name}) to {person.full_name}",
                "reason": "Nobody is responsible for it yet.",
                "params": {"task_id": str(task.id), "assignee_id": str(person.id),
                           "assignee_name": person.full_name},
            })

        for service in (
            db.query(CaseService)
            .filter(
                CaseService.business_id == business.id,
                CaseService.status.in_(OPEN_SERVICE),
                CaseService.archived_at.is_(None),
            )
            .all()
        ):
            if service.assignee_ids:
                continue
            case = db.get(FuneralCase, service.case_id)
            if case is None or case.is_archived or case.status not in LIVE:
                continue
            person = pick_person(
                db, business, permission="services.view", branch_id=case.branch_id,
                area=_area_for_text(f"{service.service_type} {service.service_name}"),
                loads=load_now(), present=present,
                text=f"{service.service_type} {service.service_name}",
            )
            if person is None:
                continue
            taken[person.id] = taken.get(person.id, 0) + 1
            out.append({
                "kind": "assign_service", "key": f"assign_service:{service.id}", "case_id": case.id,
                "summary": f"Give the service \"{service.service_name}\" ({case.deceased_full_name}) to {person.full_name}",
                "reason": "Nobody is responsible for it yet.",
                "params": {"service_id": str(service.id), "assignee_id": str(person.id),
                           "assignee_name": person.full_name},
            })
    return out


# ------------------------------------------------------------ doing it


def _log(db, business_id, action, entity_type, entity_id, details, notes):
    create_audit_log(
        db,
        business_id=business_id,
        user_id=None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details={**details, "by": "KAI Autopilot"},
        notes=notes,
    )


def _assign_task(db, business_id, task: CaseTask, person_id: UUID) -> None:
    from app.services.task_access import set_assignees

    set_assignees(db, task, [person_id], business_id=business_id, actor_id=None)


def execute(db: Session, item: KaiAutopilotItem) -> dict:
    """Do what the item says. Raises AutopilotError if it is no longer
    sensible (the world changed since it was proposed)."""

    p = item.params
    business_id = item.business_id

    if item.kind == "create_task":
        case = db.get(FuneralCase, UUID(p["case_id"]))
        if case is None or case.is_archived:
            raise AutopilotError(409, "That case is no longer open.")
        if _task_key_taken(db, case.id, p["auto_key"]):
            raise AutopilotError(409, "That task already exists.")
        due = date.fromisoformat(p["due"]) if p.get("due") else None
        task = CaseTask(
            business_id=business_id, case_id=case.id, title=p["title"],
            description=p.get("description"), status="pending", due_date=due,
            by_kai=True, auto_key=p["auto_key"],
        )
        db.add(task)
        db.flush()
        assignee = None
        if p.get("assignee_id"):
            person = db.get(User, UUID(p["assignee_id"]))
            if person is not None and person.is_active and person.business_id == business_id:
                _assign_task(db, business_id, task, person.id)
                assignee = str(person.id)
        _log(db, business_id, "case.task_created_by_kai", "case_task", task.id,
             {"title": task.title, "case_id": str(case.id)}, "KAI Autopilot created a task.")
        return {"task_id": str(task.id), "assignee_id": assignee}

    if item.kind == "assign_task":
        task = db.get(CaseTask, UUID(p["task_id"]))
        if task is None or task.business_id != business_id or task.status not in OPEN_TASK:
            raise AutopilotError(409, "That task is no longer open.")
        if task.assignee_ids or task.assigned_to:
            raise AutopilotError(409, "Someone has already been given that task.")
        person = db.get(User, UUID(p["assignee_id"]))
        if person is None or not person.is_active or person.business_id != business_id:
            raise AutopilotError(409, "That person is no longer available.")
        _assign_task(db, business_id, task, person.id)
        _log(db, business_id, "case.task_assigned_by_kai", "case_task", task.id,
             {"assignee": str(person.id)}, "KAI Autopilot gave a task to someone.")
        return {"task_id": str(task.id), "assignee_id": str(person.id)}

    if item.kind == "assign_service":
        service = db.get(CaseService, UUID(p["service_id"]))
        if service is None or service.business_id != business_id or service.status not in OPEN_SERVICE:
            raise AutopilotError(409, "That service is no longer open.")
        if service.assignee_ids:
            raise AutopilotError(409, "Someone has already been given that service.")
        person = db.get(User, UUID(p["assignee_id"]))
        if person is None or not person.is_active or person.business_id != business_id:
            raise AutopilotError(409, "That person is no longer available.")
        service.assignee_rows.append(CaseServiceAssignee(user_id=person.id))
        case = db.get(FuneralCase, service.case_id)
        notify(
            db, business_id=business_id, user_ids=[person.id],
            kind="service_assigned", title="A service was given to you",
            body=f"{service.service_name}" + (f" — {case.deceased_full_name}" if case else ""),
            link="/tasks",
        )
        _log(db, business_id, "case.service_assigned_by_kai", "case_service", service.id,
             {"assignee": str(person.id)}, "KAI Autopilot gave a service to someone.")
        return {"service_id": str(service.id), "assignee_id": str(person.id)}

    raise AutopilotError(422, "Unknown item.")


def undo(db: Session, item: KaiAutopilotItem) -> None:
    if item.status not in ("applied", "approved") or not item.result:
        raise AutopilotError(409, "There is nothing to undo.")
    r = item.result
    if item.kind == "create_task":
        task = db.get(CaseTask, UUID(r["task_id"]))
        if task is not None:
            if task.status != "pending":
                raise AutopilotError(409, "Someone has already started that task, so it stays.")
            _log(db, item.business_id, "case.task_removed_by_undo", "case_task", task.id,
                 {"title": task.title}, "An Autopilot task was undone.")
            db.delete(task)
    elif item.kind == "assign_task":
        task = db.get(CaseTask, UUID(r["task_id"]))
        if task is not None:
            task.assignee_rows[:] = []
            task.assigned_to = None
    elif item.kind == "assign_service":
        service = db.get(CaseService, UUID(r["service_id"]))
        if service is not None:
            service.assignee_rows[:] = []
    item.status = "undone"
    item.decided_at = _now()


# ------------------------------------------------------------ the run


def run(db: Session, business: Business) -> dict:
    """One pass: work out what is needed, then suggest or do it."""

    result = {"proposed": 0, "applied": 0, "escalated": 0}
    if business.autopilot_mode not in ("suggest", "auto"):
        return result

    fresh = 0
    for want in plan(db, business):
        if fresh >= MAX_PER_RUN:
            break
        if _exists(db, business.id, want["key"]):
            continue
        item = KaiAutopilotItem(
            business_id=business.id, case_id=want["case_id"], kind=want["kind"],
            status="pending", dedupe_key=want["key"], summary=want["summary"],
            reason=want["reason"], params=want["params"],
        )
        db.add(item)
        db.flush()
        fresh += 1
        if business.autopilot_mode == "auto":
            try:
                with db.begin_nested():
                    item.result = execute(db, item)
                    item.status = "applied"
                    item.decided_at = _now()
                result["applied"] += 1
            except AutopilotError:
                item.status = "dismissed"
                item.decided_at = _now()
        else:
            result["proposed"] += 1

    if business.autopilot_escalate:
        result["escalated"] = escalate_late_work(db, business)
    db.commit()
    return result


def _managers(db: Session, business_id: UUID) -> list[UUID]:
    return [
        u.id
        for u in db.query(User).filter(
            User.business_id == business_id,
            User.is_active.is_(True),
            User.role.in_(("main_admin", "manager")),
        )
    ]


def escalate_late_work(db: Session, business: Business) -> int:
    """Tell managers, once each, about work late by more than 12 hours."""

    cutoff = _now() - timedelta(hours=12)
    managers = _managers(db, business.id)
    sent = 0
    late: list[tuple[str, str, str, str]] = []
    for t in (
        db.query(CaseTask)
        .filter(CaseTask.business_id == business.id, CaseTask.status.in_(OPEN_TASK),
                CaseTask.archived_at.is_(None), CaseTask.due_at.is_not(None),
                CaseTask.due_at < cutoff)
        .all()
    ):
        late.append(("task", str(t.id), t.title, "/tasks"))
    for s in (
        db.query(CaseService)
        .filter(CaseService.business_id == business.id, CaseService.status.in_(OPEN_SERVICE),
                CaseService.archived_at.is_(None), CaseService.due_at.is_not(None),
                CaseService.due_at < cutoff)
        .all()
    ):
        late.append(("service", str(s.id), s.service_name, f"/cases/{s.case_id}/services"))
    for kind, ident, title, base in late:
        link = f"{base}?late={ident}"
        for m in managers:
            seen = (
                db.query(Notification.id)
                .filter(Notification.user_id == m, Notification.kind == "kai_escalation",
                        Notification.link == link)
                .first()
            )
            if seen:
                continue
            sent += notify(
                db, business_id=business.id, user_ids=[m], kind="kai_escalation",
                title=f"KAI: a {kind} is more than 12 hours late", body=title, link=link,
            )
    return sent


def approve(db: Session, item: KaiAutopilotItem, user_id: UUID) -> KaiAutopilotItem:
    if item.status != "pending":
        raise AutopilotError(409, f"That item was already {item.status}.")
    item.result = execute(db, item)
    item.status = "approved"
    item.decided_at = _now()
    item.decided_by = user_id
    return item


def dismiss(db: Session, item: KaiAutopilotItem, user_id: UUID) -> KaiAutopilotItem:
    if item.status != "pending":
        raise AutopilotError(409, f"That item was already {item.status}.")
    item.status = "dismissed"
    item.decided_at = _now()
    item.decided_by = user_id
    return item


def briefing(db: Session, business: Business) -> int:
    """One short summary a day for managers, only when Autopilot is on."""

    if business.autopilot_mode not in ("suggest", "auto"):
        return 0
    today = _today().isoformat()
    since = _now() - timedelta(hours=24)
    items = (
        db.query(KaiAutopilotItem)
        .filter(KaiAutopilotItem.business_id == business.id, KaiAutopilotItem.created_at >= since)
        .all()
    )
    pending = (
        db.query(func.count(KaiAutopilotItem.id))
        .filter(KaiAutopilotItem.business_id == business.id, KaiAutopilotItem.status == "pending")
        .scalar()
    )
    did = sum(1 for i in items if i.status in ("applied", "approved"))
    unassigned = (
        db.query(func.count(CaseTask.id))
        .outerjoin(CaseTaskAssignee, CaseTaskAssignee.task_id == CaseTask.id)
        .filter(CaseTask.business_id == business.id, CaseTask.status.in_(OPEN_TASK),
                CaseTask.archived_at.is_(None), CaseTaskAssignee.id.is_(None))
        .scalar()
    )
    if not (did or pending or unassigned):
        return 0
    parts = []
    if did:
        parts.append(f"I handled {did} thing(s) in the last day")
    if pending:
        parts.append(f"{pending} waiting for your approval")
    if unassigned:
        parts.append(f"{unassigned} task(s) still have nobody responsible")
    link = f"/autopilot?day={today}"
    sent = 0
    for m in _managers(db, business.id):
        if (
            db.query(Notification.id)
            .filter(Notification.user_id == m, Notification.kind == "kai_briefing",
                    Notification.link == link)
            .first()
        ):
            continue
        sent += notify(
            db, business_id=business.id, user_ids=[m], kind="kai_briefing",
            title="KAI's morning briefing", body=". ".join(parts) + ".", link=link,
        )
    db.commit()
    return sent


def run_all(db: Session) -> dict:
    total = {"proposed": 0, "applied": 0, "escalated": 0}
    for business in db.query(Business).filter(Business.is_active.is_(True)).all():
        if business.autopilot_mode not in ("suggest", "auto"):
            continue
        for key, n in run(db, business).items():
            total[key] += n
    return total


def briefing_all(db: Session) -> int:
    return sum(
        briefing(db, b)
        for b in db.query(Business).filter(Business.is_active.is_(True)).all()
    )
