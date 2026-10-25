"""
"Ask FuneralOS": plain-language questions answered from real data.

This is deliberately not a chatbot. A question is matched to one of a fixed
set of operational questions by its wording, the answer is computed with
ordinary queries, and the person only ever gets answers they could already
see on the normal screens: each question needs the permission of the screen
it comes from, and branch limits apply automatically because the queries run
inside the person's own request.
"""

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.case_financial import CaseFinancial
from app.models.case_payment import CasePayment
from app.models.case_task import CaseTask
from app.models.death_record import CasePaperworkItem
from app.models.funeral_case import FuneralCase
from app.models.member import Member
from app.models.membership import Membership
from app.models.membership_payment import MembershipPayment
from app.models.mortuary import RemainsRecord
from app.models.resource import ResourceBooking
from app.services.communications import today_in_south_africa
from app.services.permission_service import has_permission

LIVE = ("open", "confirmed", "in_progress")


def _rand(value) -> str:
    return f"R {float(value or 0):,.2f}".replace(",", " ")


def _case_item(case: FuneralCase, note: str = "") -> dict:
    return {
        "label": f"{case.deceased_full_name} ({case.case_number})"
        + (f" - {note}" if note else ""),
        "href": f"/cases/{case.id}",
    }


def _arrears(db, user):
    rows = (
        db.query(Membership, Member)
        .join(Member, Member.id == Membership.member_id)
        .filter(Membership.status == "arrears")
        .order_by(Membership.arrears_since)
        .limit(15)
        .all()
    )
    total = (
        db.query(func.count(Membership.id))
        .filter(Membership.status == "arrears")
        .scalar()
    )
    return {
        "answer": (
            f"{total} membership(s) are in arrears."
            if total else "No memberships are in arrears."
        ),
        "items": [
            {
                "label": f"{m.first_name} {m.last_name} - {ms.membership_number}"
                + (f", since {ms.arrears_since}" if ms.arrears_since else ""),
                "href": f"/members?search={m.member_number}",
            }
            for ms, m in rows
        ],
    }


def _funerals_soon(db, user):
    today = today_in_south_africa()
    end = today + timedelta(days=7)
    cases = (
        db.query(FuneralCase)
        .filter(
            FuneralCase.is_archived.is_(False),
            FuneralCase.status.in_(LIVE),
            FuneralCase.funeral_date >= today,
            FuneralCase.funeral_date <= end,
        )
        .order_by(FuneralCase.funeral_date)
        .all()
    )
    return {
        "answer": (
            f"{len(cases)} funeral(s) in the next 7 days."
            if cases else "No funerals are scheduled in the next 7 days."
        ),
        "items": [_case_item(c, str(c.funeral_date)) for c in cases],
    }


def _no_vehicle(db, user):
    today = today_in_south_africa()
    end = today + timedelta(days=7)
    cases = (
        db.query(FuneralCase)
        .filter(
            FuneralCase.is_archived.is_(False),
            FuneralCase.status.in_(LIVE),
            FuneralCase.funeral_date >= today,
            FuneralCase.funeral_date <= end,
        )
        .order_by(FuneralCase.funeral_date)
        .all()
    )
    booked = {
        row[0]
        for row in db.query(ResourceBooking.case_id)
        .filter(ResourceBooking.status == "booked")
        .all()
    }
    missing = [c for c in cases if c.id not in booked]
    return {
        "answer": (
            f"{len(missing)} funeral(s) in the next 7 days have no resource "
            "booked (vehicle, venue or equipment)."
            if missing
            else "Every funeral in the next 7 days has something booked."
        ),
        "items": [_case_item(c, str(c.funeral_date)) for c in missing],
    }


def _overdue_tasks(db, user):
    today = today_in_south_africa()
    rows = (
        db.query(CaseTask, FuneralCase)
        .join(FuneralCase, FuneralCase.id == CaseTask.case_id)
        .filter(
            CaseTask.due_date < today,
            CaseTask.status.notin_(("completed", "done", "cancelled")),
        )
        .order_by(CaseTask.due_date)
        .limit(15)
        .all()
    )
    return {
        "answer": (
            f"{len(rows)} task(s) are overdue."
            if rows else "No tasks are overdue."
        ),
        "items": [
            {
                "label": f"{t.title} - {c.deceased_full_name}, due {t.due_date}",
                "href": f"/cases/{c.id}/tasks",
            }
            for t, c in rows
        ],
    }


def _missing_paperwork(db, user):
    rows = (
        db.query(FuneralCase, func.count(CasePaperworkItem.id))
        .join(CasePaperworkItem, CasePaperworkItem.case_id == FuneralCase.id)
        .filter(
            FuneralCase.is_archived.is_(False),
            FuneralCase.status.in_(LIVE),
            CasePaperworkItem.status == "pending",
        )
        .group_by(FuneralCase.id)
        .order_by(FuneralCase.funeral_date.asc().nullslast())
        .limit(15)
        .all()
    )
    return {
        "answer": (
            f"{len(rows)} open case(s) still have paperwork outstanding."
            if rows else "No open case has paperwork outstanding."
        ),
        "items": [
            _case_item(c, f"{n} item(s) pending") for c, n in rows
        ],
    }


def _outstanding(db, user):
    total, count = (
        db.query(
            func.coalesce(func.sum(CaseFinancial.balance), 0),
            func.count(CaseFinancial.id),
        )
        .join(FuneralCase, FuneralCase.id == CaseFinancial.case_id)
        .filter(CaseFinancial.balance > 0, FuneralCase.is_archived.is_(False))
        .one()
    )
    return {
        "answer": f"{_rand(total)} is still owed on {count} case(s).",
        "items": [],
    }


def _collected(db, user):
    today = today_in_south_africa()
    start = today.replace(day=1)
    cases = (
        db.query(func.coalesce(func.sum(CasePayment.amount), 0))
        .join(FuneralCase, FuneralCase.id == CasePayment.case_id)
        .filter(CasePayment.payment_date >= start)
        .scalar()
    )
    memberships = (
        db.query(func.coalesce(func.sum(MembershipPayment.amount), 0))
        .filter(MembershipPayment.payment_date >= start)
        .scalar()
    )
    total = Decimal(cases) + Decimal(memberships)
    return {
        "answer": (
            f"{_rand(total)} collected since {start:%d %B}: "
            f"{_rand(cases)} on funerals and {_rand(memberships)} in "
            "membership contributions."
        ),
        "items": [],
    }


def _in_custody(db, user):
    rows = (
        db.query(RemainsRecord, FuneralCase)
        .join(FuneralCase, FuneralCase.id == RemainsRecord.case_id)
        .filter(RemainsRecord.status == "in_custody")
        .all()
    )
    return {
        "answer": (
            f"{len(rows)} person(s) are currently in the mortuary's care."
            if rows else "Nobody is currently in the mortuary's care."
        ),
        "items": [_case_item(c) for _, c in rows[:15]],
    }


# key, permission, words (any one matches), handler, example
QUESTIONS = [
    ("arrears", "memberships.view", ("!arrears", "behind on", "not paid up"),
     _arrears, "Which memberships are in arrears?"),
    ("no_vehicle", "resource_bookings.view",
     ("!vehicle", "!hearse", "no booking", "nothing booked", "unbooked"),
     _no_vehicle, "Which funerals this week have no vehicle booked?"),
    ("funerals_soon", "cases.view",
     ("funerals", "tomorrow", "this week", "upcoming", "coming up"),
     _funerals_soon, "What funerals are coming up?"),
    ("overdue_tasks", "tasks.view", ("!overdue", "late task", "behind schedule"),
     _overdue_tasks, "Which tasks are overdue?"),
    ("paperwork", "paperwork.view",
     ("!paperwork", "documents missing", "missing documents", "missing"),
     _missing_paperwork, "Which cases have paperwork outstanding?"),
    ("collected", "financials.view",
     ("!collected", "took in", "!income", "!revenue", "received"),
     _collected, "What was collected this month?"),
    ("outstanding", "financials.view",
     ("!outstanding", "!owed", "!owing", "!unpaid", "balance"),
     _outstanding, "How much is outstanding on funerals?"),
    ("custody", "remains.view",
     ("!custody", "!mortuary", "in our care", "fridge", "remains"),
     _in_custody, "Who is in the mortuary right now?"),
]


def available(db: Session, user: dict) -> list[dict]:
    return [
        {"key": key, "example": example}
        for key, perm, _, _, example in QUESTIONS
        if has_permission(
            db, user_id=user["user_id"], role=user["role"], permission_key=perm
        )
    ]


def _score(question: str, words) -> int:
    q = question.lower()
    # A word starting with "!" is a strong signal and counts five.
    return sum(
        5 if w.startswith("!") else 1
        for w in words
        if w.lstrip("!") in q
    )


def ask(db: Session, user: dict, question: str) -> dict:
    q = question.strip()
    best = None
    for entry in QUESTIONS:
        score = _score(q, entry[2])
        if score and (best is None or score > best[0]):
            best = (score, entry)

    if best is None:
        return {
            "understood": False,
            "answer": "I can answer questions like the ones below.",
            "items": [],
            "suggestions": available(db, user),
        }

    _, (key, perm, _, handler, _) = best
    if not has_permission(
        db, user_id=user["user_id"], role=user["role"], permission_key=perm
    ):
        return {
            "understood": True,
            "answer": "You do not have access to that information.",
            "items": [],
            "suggestions": available(db, user),
        }
    result = handler(db, user)
    return {"understood": True, "question": key, **result, "suggestions": []}
