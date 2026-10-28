"""KAI - Knowledge, Assistance, Intelligence.

The colleague inside FuneralOS. KAI greets people by name, knows their
role and branch, follows a conversation ("the second one", "that case"),
works out what is missing on a case, and prepares actions for the person
to confirm.

How it stays trustworthy:

* Everything it says comes from a fresh query run inside the person's own
  request, so branch limits and permissions apply exactly as on the normal
  screens. Each kind of answer also needs the permission of its screen.
* Conversation memory holds ids only (which case was being discussed), per
  person. Facts are looked up again, with the person's current access,
  every time. If access is gone, KAI says so instead of remembering.
* KAI never changes anything by itself. It prepares an action, shows what
  it would do, and only runs it when the person confirms - re-checking
  their permission at that moment.
* It never invents: when it cannot find or is not allowed to see
  something, it says that.
"""

import re
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.branch import Branch
from app.models.case_financial import CaseFinancial
from app.models.case_task import CaseTask
from app.models.death_record import CasePaperworkItem, DeathRecord
from app.models.funeral_case import FuneralCase
from app.models.kai import KaiAction, KaiTurn
from app.models.mortuary import RemainsRecord
from app.models.resource import Resource, ResourceBooking
from app.models.transport import TransportJob
from app.models.user import User
from app.services import assistant as legacy
from app.services.communications import today_in_south_africa
from app.services.mortuary import release_blockers
from app.services.permission_service import has_permission

SA = timezone(timedelta(hours=2))
LIVE = ("open", "confirmed", "in_progress")
ACTION_MINUTES = 15
KEEP_TURNS = 200

CASE_ID = re.compile(r"/cases/([0-9a-fA-F-]{36})")
ORDINALS = {
    "first": 0, "1st": 0, "second": 1, "2nd": 1, "third": 2, "3rd": 2,
    "fourth": 3, "4th": 3, "fifth": 4, "5th": 4, "last": -1,
}
ORDINAL_RE = re.compile(r"\b(" + "|".join(ORDINALS) + r")\b", re.I)
PRONOUN_RE = re.compile(
    r"\b(that|this|the same|current)\s+(case|funeral|person|one|family)\b"
    r"|\b(him|her|them|it|his|their)\b",
    re.I,
)
ORG_WIDE_RE = re.compile(
    r"\ball (our |the )?branches\b|\bevery branch\b|\bacross (all |the )?"
    r"branches\b|\bwhole organi[sz]ation\b|\borgani[sz]ation[- ]wide\b"
    r"|\beach branch\b|\bby branch\b|\bper branch\b|\bcompare branches\b"
    r"|\bbranch comparison\b|\bbranch breakdown\b",
    re.I,
)
NAME_STOP = {
    "is", "what", "which", "how", "who", "show", "tell", "can", "please",
    "kai", "hello", "hi", "hey", "the", "i", "are", "do", "does", "when",
    "where", "create", "make", "add", "check", "let", "give", "list",
    "find", "thanks", "thank", "morning", "good", "ok", "okay", "yes",
    "no", "and", "for", "about", "of", "on", "a", "an",
}


def _can(db: Session, user: dict, permission: str) -> bool:
    return has_permission(
        db, user_id=user["user_id"], role=user["role"], permission_key=permission
    )


# ============================================================
# WHO IS ASKING
# ============================================================

def context(db: Session, user: dict) -> dict:
    """Verified facts about the signed-in person, from the database."""

    person = db.get(User, user["user_id"])
    all_branches = _can(db, user, "branches.all_access")
    branch_name = None
    if person is not None and person.branch_id is not None:
        branch = db.get(Branch, person.branch_id)
        branch_name = branch.name if branch else None
    name = (person.full_name if person else "").strip()
    return {
        "name": name,
        "first_name": name.split()[0] if name else "",
        "job_title": person.job_title if person else None,
        "role": user["role"],
        "branch_name": branch_name,
        "all_branches": all_branches,
    }


def _greeting_word() -> str:
    hour = datetime.now(SA).hour
    if hour < 12:
        return "Morning"
    if hour < 18:
        return "Afternoon"
    return "Evening"


# ============================================================
# MEMORY (ids only, one person)
# ============================================================

def _last_focus(db: Session, user: dict) -> dict:
    turn = (
        db.query(KaiTurn)
        .filter(
            KaiTurn.user_id == user["user_id"],
            KaiTurn.business_id == user["business_id"],
            KaiTurn.speaker == "kai",
        )
        .order_by(KaiTurn.created_at.desc())
        .first()
    )
    return dict(turn.focus) if turn and turn.focus else {}


def _remember(db, user, speaker, text, items=None, focus=None):
    db.add(
        KaiTurn(
            business_id=user["business_id"],
            user_id=user["user_id"],
            speaker=speaker,
            text=text,
            items=items or [],
            focus=focus or {},
        )
    )
    db.flush()
    old = (
        db.query(KaiTurn.id)
        .filter(KaiTurn.user_id == user["user_id"])
        .order_by(KaiTurn.created_at.desc())
        .offset(KEEP_TURNS)
        .all()
    )
    if old:
        db.query(KaiTurn).filter(
            KaiTurn.id.in_([row[0] for row in old])
        ).delete(synchronize_session=False)


def history(db: Session, user: dict, limit: int = 40) -> list[dict]:
    rows = (
        db.query(KaiTurn)
        .filter(
            KaiTurn.user_id == user["user_id"],
            KaiTurn.business_id == user["business_id"],
        )
        .order_by(KaiTurn.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "speaker": row.speaker,
            "text": row.text,
            "items": row.items,
            "created_at": row.created_at,
        }
        for row in reversed(rows)
    ]


def clear_history(db: Session, user: dict) -> None:
    db.query(KaiTurn).filter(KaiTurn.user_id == user["user_id"]).delete()
    db.commit()


# ============================================================
# FINDING THE CASE BEING TALKED ABOUT
# ============================================================

def _case(db: Session, user: dict, case_id) -> FuneralCase | None:
    """Looked up now, inside the person's branch scope."""
    try:
        case_id = UUID(str(case_id))
    except ValueError:
        return None
    return (
        db.query(FuneralCase)
        .filter(
            FuneralCase.id == case_id,
            FuneralCase.business_id == user["business_id"],
        )
        .first()
    )


def _case_ids(items) -> list[str]:
    ids = []
    for item in items:
        match = CASE_ID.search(item.get("href", ""))
        if match:
            ids.append(match.group(1))
    return ids


def resolve_case(db: Session, user: dict, text: str, focus: dict):
    """Returns ("case", case) | ("many", [cases]) | ("missing", why) | ("notfound", name) | None."""

    # A case number typed out.
    for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9\-/]{3,}", text):
        if any(ch.isdigit() for ch in token) and "-" in token:
            found = (
                db.query(FuneralCase)
                .filter(
                    FuneralCase.business_id == user["business_id"],
                    func.upper(FuneralCase.case_number) == token.upper(),
                )
                .first()
            )
            if found:
                return "case", found

    # "the second one" - relative to the last list KAI showed.
    ordinal = ORDINAL_RE.search(text)
    if ordinal:
        listed = focus.get("cases") or []
        if not listed:
            return "missing", "there is no list in front of us yet"
        index = ORDINALS[ordinal.group(1).lower()]
        try:
            case_id = listed[index]
        except IndexError:
            return "missing", "that position is not in the list"
        found = _case(db, user, case_id)
        if found is None:
            return "missing", "I can no longer open that record"
        return "case", found

    # A name.
    words = re.findall(r"\b[A-Z][a-zA-Z'\-]+\b", text)
    names = [w for w in words if w.lower() not in NAME_STOP]
    if names:
        query = db.query(FuneralCase).filter(
            FuneralCase.business_id == user["business_id"],
            FuneralCase.is_archived.is_(False),
        )
        for word in names[:3]:
            query = query.filter(
                FuneralCase.deceased_full_name.ilike(f"%{word}%")
            )
        matches = query.order_by(FuneralCase.created_at.desc()).limit(6).all()
        if len(matches) == 1:
            return "case", matches[0]
        if len(matches) > 1:
            return "many", matches
        return "notfound", " ".join(names[:3])

    # "that case", "him", "it" - the one we were already discussing.
    if PRONOUN_RE.search(text):
        case_id = focus.get("case_id")
        if not case_id and len(focus.get("cases") or []) == 1:
            case_id = focus["cases"][0]
        if not case_id:
            return "missing", "I'm not sure which case you mean"
        found = _case(db, user, case_id)
        if found is None:
            return "missing", "I can no longer open that record"
        return "case", found

    return None


def _item(case: FuneralCase, note: str = "") -> dict:
    return {
        "label": f"{case.deceased_full_name} ({case.case_number})"
        + (f" - {note}" if note else ""),
        "href": f"/cases/{case.id}",
    }


# ============================================================
# WHAT IS MISSING ON A CASE
# ============================================================

def case_gaps(db: Session, user: dict, case: FuneralCase) -> list[dict]:
    """Real, current gaps - only the kinds this person may see."""

    gaps: list[dict] = []
    today = today_in_south_africa()
    base = f"/cases/{case.id}"
    live = case.status in LIVE and not case.is_archived

    if live and case.funeral_date is None and _can(db, user, "cases.view"):
        gaps.append({"label": "No funeral date has been set", "href": base})

    if _can(db, user, "paperwork.view"):
        pending = (
            db.query(CasePaperworkItem)
            .filter(
                CasePaperworkItem.case_id == case.id,
                CasePaperworkItem.status == "pending",
            )
            .all()
        )
        for entry in pending:
            gaps.append({
                "label": "Paperwork not yet obtained: "
                + entry.item_type.replace("_", " "),
                "href": f"{base}/documents",
            })

    if _can(db, user, "tasks.view"):
        open_tasks = (
            db.query(CaseTask)
            .filter(
                CaseTask.case_id == case.id,
                CaseTask.status.notin_(("completed", "done", "cancelled")),
            )
            .all()
        )
        for task in open_tasks:
            late = task.due_date is not None and task.due_date < today
            gaps.append({
                "label": (
                    f"Task overdue (due {task.due_date}): {task.title}"
                    if late else f"Open task: {task.title}"
                ),
                "href": f"{base}/tasks",
            })

    if _can(db, user, "financials.view"):
        owed = (
            db.query(CaseFinancial.balance)
            .filter(CaseFinancial.case_id == case.id)
            .scalar()
        )
        if owed and owed > 0:
            gaps.append({
                "label": f"{legacy._rand(owed)} is still owed on this case",
                "href": f"{base}/financial",
            })

    soon = (
        live and case.funeral_date is not None
        and today <= case.funeral_date <= today + timedelta(days=14)
    )
    if soon and _can(db, user, "resource_bookings.view"):
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
            gaps.append({
                "label": "No vehicle is booked for the funeral",
                "href": "/resource-bookings",
            })

    if live and _can(db, user, "transport.view"):
        unfilled = (
            db.query(func.count(TransportJob.id))
            .filter(
                TransportJob.case_id == case.id,
                TransportJob.status == "open",
            )
            .scalar()
        )
        if unfilled:
            gaps.append({
                "label": f"{unfilled} family car job(s) have no driver yet",
                "href": "/transport",
            })

    return gaps


def _case_summary(db, user, case):
    gaps = case_gaps(db, user, case)
    when = f", funeral on {case.funeral_date:%d %B %Y}" if case.funeral_date else ""
    head = (
        f"{case.deceased_full_name} ({case.case_number}) is "
        f"{case.status.replace('_', ' ')}{when}."
    )
    if gaps:
        text = f"{head} I can see {len(gaps)} thing(s) that need attention."
    else:
        text = f"{head} I don't see anything outstanding on what I can access."
    return {
        "reply": text,
        "items": gaps[:8] or [_item(case)],
        "focus": {"case_id": str(case.id)},
    }


def _case_missing(db, user, case):
    gaps = case_gaps(db, user, case)
    if not gaps:
        return {
            "reply": (
                f"Nothing looks outstanding on {case.deceased_full_name}'s "
                "case from the records I can access."
            ),
            "items": [_item(case)],
            "focus": {"case_id": str(case.id)},
        }
    return {
        "reply": (
            f"Here is what is outstanding on {case.deceased_full_name}'s "
            f"case. Want me to prepare a follow-up task for \"{gaps[0]['label']}\"?"
        ),
        "items": gaps[:10],
        "focus": {"case_id": str(case.id)},
    }


def _collection(db, user, case):
    if not _can(db, user, "remains.view"):
        return _denied()
    remains = (
        db.query(RemainsRecord).filter(RemainsRecord.case_id == case.id).first()
    )
    focus = {"case_id": str(case.id)}
    if remains is None:
        return {
            "reply": (
                f"There is no mortuary record for {case.deceased_full_name} "
                "yet, so I can't say anything about collection."
            ),
            "items": [_item(case)],
            "focus": focus,
        }
    if remains.status == "released":
        return {
            "reply": (
                f"{case.deceased_full_name} has already been released"
                + (f" on {remains.released_at:%d %B %Y}." if remains.released_at else ".")
            ),
            "items": [_item(case)],
            "focus": focus,
        }
    death = (
        db.query(DeathRecord).filter(DeathRecord.case_id == case.id).first()
    )
    paperwork = (
        db.query(CasePaperworkItem)
        .filter(CasePaperworkItem.case_id == case.id)
        .all()
    )
    blockers = release_blockers(
        remains=remains, death_record=death, paperwork_items=paperwork
    )
    if blockers:
        return {
            "reply": (
                "Being in the mortuary's care doesn't mean ready for "
                "collection. I wouldn't mark this one ready yet - the record "
                "still shows:"
            ),
            "items": [
                {"label": b, "href": f"/cases/{case.id}/remains"}
                for b in blockers
            ],
            "focus": focus,
        }
    return {
        "reply": (
            "Everything the record requires for release is in place. "
            "Checking the person's identity and the collector at the door "
            "still rests with your team."
        ),
        "items": [_item(case)],
        "focus": focus,
    }


def _denied():
    return {
        "reply": (
            "I can't help with that from your current access. If you need "
            "it for your duties, your manager can review your permissions."
        ),
        "items": [],
        "focus": {},
    }


def _balance(db, user, case):
    if not _can(db, user, "financials.view"):
        return _denied()
    row = (
        db.query(CaseFinancial).filter(CaseFinancial.case_id == case.id).first()
    )
    if row is None:
        return {
            "reply": "There are no financial figures on this case yet.",
            "items": [_item(case)],
            "focus": {"case_id": str(case.id)},
        }
    return {
        "reply": (
            f"{case.deceased_full_name}'s case: {legacy._rand(row.balance)} "
            "still owed."
            if row.balance and row.balance > 0
            else f"{case.deceased_full_name}'s case has nothing outstanding."
        ),
        "items": [{"label": "Open financial summary",
                   "href": f"/cases/{case.id}/financial"}],
        "focus": {"case_id": str(case.id)},
    }


# ============================================================
# PREPARING AN ACTION (never run without confirmation)
# ============================================================

def _prepare_task(db, user, case, text):
    if not _can(db, user, "tasks.manage"):
        return _denied()
    title = None
    match = re.search(r"task\s*(?:to|:|-|for)\s+(.+)$", text, re.I)
    if match:
        title = match.group(1).strip().rstrip(".?!")
    if not title:
        gaps = case_gaps(db, user, case)
        title = f"Follow up: {gaps[0]['label']}" if gaps else "Follow up on this case"
    title = title[:200]
    summary = f"Add the task \"{title}\" to {case.deceased_full_name}'s case"
    action = KaiAction(
        business_id=user["business_id"],
        user_id=user["user_id"],
        kind="create_task",
        params={"case_id": str(case.id), "title": title},
        summary=summary,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=ACTION_MINUTES),
    )
    db.add(action)
    db.flush()
    return {
        "reply": f"I've prepared this for you to review: {summary}. Shall I go ahead?",
        "items": [_item(case)],
        "focus": {"case_id": str(case.id)},
        "action": {"id": str(action.id), "summary": summary},
    }


def _load_action(db, user, action_id) -> KaiAction | None:
    try:
        action_id = UUID(str(action_id))
    except ValueError:
        return None
    return (
        db.query(KaiAction)
        .filter(
            KaiAction.id == action_id,
            KaiAction.user_id == user["user_id"],
            KaiAction.business_id == user["business_id"],
        )
        .first()
    )


def confirm_action(db: Session, user: dict, action_id) -> dict:
    action = _load_action(db, user, action_id)
    if action is None:
        return {"ok": False, "reply": "I can't find that action."}
    if action.status != "pending":
        return {"ok": False, "reply": f"That action was already {action.status}."}
    if action.expires_at < datetime.now(timezone.utc):
        action.status = "expired"
        db.commit()
        return {"ok": False, "reply": "That took too long, so I dropped it. Ask me again and I'll prepare it afresh."}

    if action.kind == "create_task":
        # The permission and the case are checked again right now.
        if not _can(db, user, "tasks.manage"):
            return {"ok": False, "reply": "Your access no longer lets you add tasks, so I haven't done it."}
        case = _case(db, user, action.params["case_id"])
        if case is None:
            return {"ok": False, "reply": "I can no longer open that case, so I haven't added the task."}
        from app.api.tasks import create_task
        from app.schemas.case_task import CaseTaskCreate

        try:
            create_task(case.id, CaseTaskCreate(title=action.params["title"]), db, user)
        except Exception as error:  # report what really happened
            db.rollback()
            detail = getattr(error, "detail", None) or "something went wrong"
            return {"ok": False, "reply": f"I couldn't add the task: {detail}"}
        action = _load_action(db, user, action_id)
        action.status = "done"
        reply = f"Done - the task \"{action.params['title']}\" is on {case.deceased_full_name}'s case."
        _remember(db, user, "kai", reply, [_item(case)], {"case_id": str(case.id)})
        db.commit()
        return {"ok": True, "reply": reply, "items": [_item(case)]}

    return {"ok": False, "reply": "I don't know how to do that action."}


def cancel_action(db: Session, user: dict, action_id) -> dict:
    action = _load_action(db, user, action_id)
    if action is None or action.status != "pending":
        return {"ok": False, "reply": "There's nothing pending to cancel."}
    action.status = "cancelled"
    db.commit()
    return {"ok": True, "reply": "No problem - I've left it alone."}


# ============================================================
# ORGANISATION VIEW (only with branches.all_access)
# ============================================================

def _branch_overview(db, user):
    today = today_in_south_africa()
    end = today + timedelta(days=7)
    branches = {
        b.id: b.name
        for b in db.query(Branch).filter(Branch.business_id == user["business_id"])
    }
    live = dict(
        db.query(FuneralCase.branch_id, func.count(FuneralCase.id))
        .filter(
            FuneralCase.business_id == user["business_id"],
            FuneralCase.is_archived.is_(False),
            FuneralCase.status.in_(LIVE),
        )
        .group_by(FuneralCase.branch_id)
        .all()
    )
    soon = dict(
        db.query(FuneralCase.branch_id, func.count(FuneralCase.id))
        .filter(
            FuneralCase.business_id == user["business_id"],
            FuneralCase.is_archived.is_(False),
            FuneralCase.status.in_(LIVE),
            FuneralCase.funeral_date >= today,
            FuneralCase.funeral_date <= end,
        )
        .group_by(FuneralCase.branch_id)
        .all()
    )
    paper = dict(
        db.query(FuneralCase.branch_id, func.count(func.distinct(FuneralCase.id)))
        .join(CasePaperworkItem, CasePaperworkItem.case_id == FuneralCase.id)
        .filter(
            FuneralCase.business_id == user["business_id"],
            FuneralCase.is_archived.is_(False),
            FuneralCase.status.in_(LIVE),
            CasePaperworkItem.status == "pending",
        )
        .group_by(FuneralCase.branch_id)
        .all()
    )
    keys = sorted(
        set(live) | set(soon) | set(paper),
        key=lambda k: branches.get(k, "~"),
    )
    items = [
        {
            "label": f"{branches.get(k, 'No branch')}: {live.get(k, 0)} open case(s), "
            f"{soon.get(k, 0)} funeral(s) in 7 days, "
            f"{paper.get(k, 0)} with paperwork outstanding",
            "href": "/cases",
        }
        for k in keys
    ]
    return {
        "reply": (
            f"Here's the picture across {len(keys)} branch(es), read from the "
            "records just now."
            if keys else "There are no open cases in any branch right now."
        ),
        "items": items,
        "focus": {},
    }


# ============================================================
# MATCHING WHAT THE PERSON ASKED
# ============================================================

def _score(text: str, words) -> int:
    return legacy._score(text, words)


CASE_INTENTS = [
    ("collection", ("!collect", "!release", "!ready for", "ready to go"), _collection),
    ("missing", ("!missing", "!outstanding", "!incomplete", "!follow up",
                 "!follow-up", "what's left", "whats left", "next step",
                 "what should i do", "what needs", "!gaps"), _case_missing),
    ("balance", ("!owe", "!balance", "!paid", "!payment"), _balance),
]


def _list_intent(db, user, text):
    best = None
    for entry in legacy.QUESTIONS:
        score = _score(text, entry[2])
        if score and (best is None or score > best[0]):
            best = (score, entry)
    if best is None:
        return None
    _, (key, permission, _, handler, _) = best
    if not _can(db, user, permission):
        return _denied()
    result = handler(db, user)
    ids = _case_ids(result.get("items", []))
    return {
        "reply": result["answer"],
        "items": result.get("items", []),
        "focus": {"cases": ids} if ids else {},
    }


def examples(db: Session, user: dict) -> list[str]:
    out = [row["example"] for row in legacy.available(db, user)]
    if _can(db, user, "cases.view"):
        out.append("What needs attention today?")
    return out[:8]


def _attention(db, user):
    topics = _briefing_topics(db, user)
    flat = [item for _, _, items in topics for item in items]
    ids = []
    for item in flat:
        for case_id in _case_ids([item]):
            if case_id not in ids:
                ids.append(case_id)
    if not ids:
        return {
            "reply": "Nothing stands out right now from what I can access.",
            "items": [], "focus": {},
        }
    first = _case(db, user, ids[0])
    result = _case_missing(db, user, first) if first else {"reply": "", "items": []}
    result["focus"] = {"case_id": ids[0], "cases": ids}
    result["reply"] = (
        f"Let's start with {first.deceased_full_name} ({first.case_number}). "
        + result["reply"]
    )
    return result


def message(db: Session, user: dict, text: str) -> dict:
    text = text.strip()
    focus = _last_focus(db, user)
    ctx = context(db, user)
    _remember(db, user, "user", text)

    result = _answer(db, user, text, focus, ctx)
    result.setdefault("items", [])
    result.setdefault("focus", {})
    reply_focus = result["focus"] or {}
    if not reply_focus.get("cases") and not reply_focus.get("case_id"):
        reply_focus = {}
    _remember(db, user, "kai", result["reply"], result["items"], reply_focus)
    db.commit()
    return {
        "reply": result["reply"],
        "items": result["items"],
        "action": result.get("action"),
        "suggestions": result.get("suggestions", []),
    }


def _answer(db, user, text, focus, ctx):
    lowered = text.lower()

    greeting = re.fullmatch(r"(hi|hello|hey|morning|good (morning|afternoon|evening))[ ,!.]*(kai)?[!. ]*", lowered)
    if greeting:
        return {"reply": f"{_greeting_word()}, {ctx['first_name'] or 'there'}! What can I help with?",
                "suggestions": examples(db, user)}

    # Organisation-wide asks follow the person's real authority.
    if ORG_WIDE_RE.search(text):
        if not ctx["all_branches"]:
            return {
                "reply": (
                    "I can help you review the cases within your access. I can't "
                    "provide the organisation-wide view from your current "
                    "permissions. If you need wider access for your duties, your "
                    "authorised manager can review your access."
                ),
                "suggestions": examples(db, user),
            }
        if re.search(r"branch|organi[sz]ation|compare|overview", lowered):
            return _branch_overview(db, user)

    if re.search(r"needs? (my |our )?attention|what.s urgent|needs me", lowered):
        return _attention(db, user)

    ref = resolve_case(db, user, text, focus)

    if ref is not None and ref[0] == "notfound":
        listed = _list_intent(db, user, text)
        if listed is not None:
            return listed
        return {
            "reply": f"I couldn't find a case for {ref[1]}. Check the spelling, or try the case number.",
            "suggestions": examples(db, user),
        }

    if ref is not None:
        kind, value = ref
        if kind == "missing":
            return {"reply": f"{value[0].upper()}{value[1:]}. Could you tell me which case - a name or case number works.",
                    "suggestions": examples(db, user)}
        if kind == "many":
            return {
                "reply": "There's more than one match. Which of these do you mean?",
                "items": [_item(c) for c in value],
                "focus": {"cases": [str(c.id) for c in value]},
            }
        case = value
        if re.search(r"\b(task|remind)\b", lowered) and re.search(r"\b(create|add|make|prepare|set up|new)\b", lowered):
            return _prepare_task(db, user, case, text)
        if not _can(db, user, "cases.view"):
            return _denied()
        best = None
        for key, words, handler in CASE_INTENTS:
            score = _score(text, words)
            if score and (best is None or score > best[0]):
                best = (score, handler)
        if best:
            return best[1](db, user, case)
        return _case_summary(db, user, case)

    # A task with no case named: use the one we were discussing.
    if re.search(r"\b(task|remind)\b", lowered) and re.search(r"\b(create|add|make|prepare)\b", lowered):
        case = _case(db, user, focus.get("case_id")) if focus.get("case_id") else None
        if case is None:
            return {"reply": "Which case should the task go on? Tell me a name or case number."}
        return _prepare_task(db, user, case, text)

    listed = _list_intent(db, user, text)
    if listed is not None:
        return listed

    return {
        "reply": (
            "I'm not sure I followed that. I can look into cases, the "
            "mortuary, payments, tasks and the schedule. Try one of these:"
        ),
        "suggestions": examples(db, user),
    }


# ============================================================
# GREETING AND BRIEFING
# ============================================================

def _briefing_topics(db, user):
    """(key, answer, items) for things that really need a look."""
    topics = []
    plan = [
        ("overdue_tasks", "tasks.view", legacy._overdue_tasks),
        ("no_vehicle", "resource_bookings.view", legacy._no_vehicle),
        ("paperwork", "paperwork.view", legacy._missing_paperwork),
    ]
    for key, permission, handler in plan:
        if not _can(db, user, permission):
            continue
        result = handler(db, user)
        if result.get("items"):
            topics.append((key, result["answer"], result["items"]))

    if _can(db, user, "transport.view"):
        today = today_in_south_africa()
        start = datetime.combine(today, datetime.min.time(), tzinfo=SA)
        jobs = (
            db.query(TransportJob)
            .filter(
                TransportJob.status == "open",
                TransportJob.report_time >= start,
                TransportJob.report_time < start + timedelta(days=7),
            )
            .all()
        )
        if jobs:
            items = []
            for job in jobs[:10]:
                case = _case(db, user, job.case_id)
                if case is not None:
                    items.append(_item(case, f"{job.label} needs a driver"))
            if items:
                topics.append((
                    "car_jobs",
                    f"{len(jobs)} family car job(s) in the next 7 days have no driver yet.",
                    items,
                ))
    return topics


def hello(db: Session, user: dict) -> dict:
    ctx = context(db, user)
    topics = _briefing_topics(db, user)

    who = ctx["first_name"] or "there"
    parts = [f"{_greeting_word()}, {who}! Welcome back."]
    if ctx["all_branches"]:
        parts.append("You have access across all branches.")
    elif ctx["branch_name"]:
        parts.append(f"You're on the {ctx['branch_name']} branch today.")
    else:
        parts.append(
            "I couldn't confirm your assigned branch from your account. I can "
            "still help with the information you're authorised to access, but "
            "your branch assignment may need to be checked."
        )

    if topics:
        parts.append("Here's what I'd keep an eye on: " + " ".join(t[1] for t in topics[:3]))
        parts.append("Want to start with the first one?")
    else:
        parts.append("Nothing needs urgent attention from what I can see. What would you like to do?")

    flat = [item for _, _, items in topics for item in items]
    ids = []
    for case_id in _case_ids(flat):
        if case_id not in ids:
            ids.append(case_id)
    text = " ".join(parts)
    _remember(db, user, "kai", text, flat[:8], {"cases": ids} if ids else {})
    db.commit()
    return {
        "reply": text,
        "name": ctx["name"],
        "role": ctx["role"],
        "job_title": ctx["job_title"],
        "branch": "All branches" if ctx["all_branches"] else ctx["branch_name"],
        "briefing": [
            {"key": key, "text": answer, "items": items[:5]}
            for key, answer, items in topics
        ],
        "suggestions": examples(db, user),
    }
