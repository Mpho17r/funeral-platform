"""
One search box for the whole business.

Each kind of record is only searched when the person holds the permission
that lets them open it, so search never shows something the rest of the
app would refuse. Results are small previews with the screen to open.
"""

from uuid import UUID

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.case_contact import CaseContact
from app.models.expense import Expense
from app.models.funeral_case import FuneralCase
from app.models.inventory import Supplier
from app.models.member import Member
from app.models.membership import Membership
from app.services.permission_service import effective_permissions

PER_GROUP = 5
MIN_LENGTH = 2


def _like(text: str) -> str:
    """Escape LIKE wildcards so a typed % or _ is searched literally."""
    escaped = (
        text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    )
    return f"%{escaped}%"


def _phone_like(text: str) -> str | None:
    digits = "".join(ch for ch in text if ch.isdigit())
    return _like(digits) if len(digits) >= 3 else None


def _name_match(first, last, text):
    return func.concat(first, " ", last).ilike(_like(text), escape="\\")


def search(
    db: Session,
    *,
    business_id: UUID,
    user_id: UUID,
    role: str,
    query: str,
) -> dict:
    text = query.strip()
    if len(text) < MIN_LENGTH:
        return {"query": text, "groups": []}

    held = set(effective_permissions(db, user_id=user_id, role=role))
    pattern = _like(text)
    phone = _phone_like(text)
    groups: list[dict] = []

    def add(key, label, items):
        if items:
            groups.append({"key": key, "label": label, "items": items})

    if "cases.view" in held:
        rows = (
            db.query(FuneralCase)
            .filter(
                FuneralCase.business_id == business_id,
                or_(
                    FuneralCase.case_number.ilike(pattern, escape="\\"),
                    FuneralCase.deceased_full_name.ilike(
                        pattern, escape="\\"
                    ),
                ),
            )
            .order_by(FuneralCase.is_archived, FuneralCase.created_at.desc())
            .limit(PER_GROUP)
            .all()
        )
        add(
            "cases",
            "Funerals",
            [
                {
                    "id": str(c.id),
                    "title": c.deceased_full_name,
                    "subtitle": c.case_number
                    + (" · archived" if c.is_archived else ""),
                    "href": f"/cases/{c.id}",
                }
                for c in rows
            ],
        )

    if "members.view" in held:
        conditions = [
            _name_match(Member.first_name, Member.last_name, text),
            Member.member_number.ilike(pattern, escape="\\"),
            Member.email.ilike(pattern, escape="\\"),
        ]
        if phone:
            conditions.append(
                func.replace(Member.phone, " ", "").ilike(
                    phone, escape="\\"
                )
            )
        rows = (
            db.query(Member)
            .filter(
                Member.business_id == business_id,
                Member.archived_at.is_(None),
                or_(*conditions),
            )
            .order_by(Member.last_name, Member.first_name)
            .limit(PER_GROUP)
            .all()
        )
        add(
            "members",
            "Members",
            [
                {
                    "id": str(m.id),
                    "title": f"{m.first_name} {m.last_name}",
                    "subtitle": f"{m.member_number}"
                    + (f" · {m.phone}" if m.phone else ""),
                    "href": f"/members?search={m.member_number}",
                }
                for m in rows
            ],
        )

    if "memberships.view" in held:
        rows = (
            db.query(Membership, Member)
            .join(Member, Member.id == Membership.member_id)
            .filter(
                Membership.business_id == business_id,
                or_(
                    Membership.membership_number.ilike(
                        pattern, escape="\\"
                    ),
                    _name_match(Member.first_name, Member.last_name, text),
                ),
            )
            .order_by(Membership.created_at.desc())
            .limit(PER_GROUP)
            .all()
        )
        add(
            "memberships",
            "Memberships",
            [
                {
                    "id": str(ms.id),
                    "title": ms.membership_number,
                    "subtitle": f"{m.first_name} {m.last_name} · "
                    f"{ms.status.replace('_', ' ')}",
                    "href": "/memberships",
                }
                for ms, m in rows
            ],
        )

    if "contacts.view" in held or "families.view" in held:
        conditions = [
            _name_match(CaseContact.first_name, CaseContact.last_name, text),
            CaseContact.email.ilike(pattern, escape="\\"),
        ]
        if phone:
            conditions.append(
                func.replace(CaseContact.phone, " ", "").ilike(
                    phone, escape="\\"
                )
            )
        rows = (
            db.query(CaseContact, FuneralCase)
            .join(FuneralCase, FuneralCase.id == CaseContact.case_id)
            .filter(
                CaseContact.business_id == business_id,
                FuneralCase.business_id == business_id,
                or_(*conditions),
            )
            .order_by(CaseContact.created_at.desc())
            .limit(PER_GROUP)
            .all()
        )
        can_open = "cases.view" in held
        add(
            "contacts",
            "Family and contacts",
            [
                {
                    "id": str(c.id),
                    "title": f"{c.first_name} {c.last_name or ''}".strip(),
                    "subtitle": " · ".join(
                        part
                        for part in (
                            c.relationship,
                            f"for {case.deceased_full_name}",
                            c.phone,
                        )
                        if part
                    ),
                    "href": f"/cases/{case.id}" if can_open else "/contacts",
                }
                for c, case in rows
            ],
        )

    if "suppliers.view" in held:
        rows = (
            db.query(Supplier)
            .filter(
                Supplier.business_id == business_id,
                or_(
                    Supplier.name.ilike(pattern, escape="\\"),
                    Supplier.contact_person.ilike(pattern, escape="\\"),
                ),
            )
            .order_by(Supplier.name)
            .limit(PER_GROUP)
            .all()
        )
        add(
            "suppliers",
            "Suppliers",
            [
                {
                    "id": str(s.id),
                    "title": s.name,
                    "subtitle": s.contact_person or "",
                    "href": "/suppliers",
                }
                for s in rows
            ],
        )

    if "expenses.view" in held:
        rows = (
            db.query(Expense)
            .filter(
                Expense.business_id == business_id,
                or_(
                    Expense.description.ilike(pattern, escape="\\"),
                    Expense.reference.ilike(pattern, escape="\\"),
                ),
            )
            .order_by(Expense.expense_date.desc())
            .limit(PER_GROUP)
            .all()
        )
        add(
            "expenses",
            "Expenses",
            [
                {
                    "id": str(e.id),
                    "title": e.description,
                    "subtitle": f"R {float(e.amount):,.2f} · "
                    f"{e.expense_date.isoformat()}"
                    + (" · voided" if e.status == "voided" else ""),
                    "href": "/expenses",
                }
                for e in rows
            ],
        )

    return {"query": text, "groups": groups}
