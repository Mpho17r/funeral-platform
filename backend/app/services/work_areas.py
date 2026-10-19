"""Work areas: what a staff member does at the business.

A work area narrows a staff account to the permissions of their job,
so a mortuary worker never sees money and a finance clerk never sees
the mortuary. It replaces the generic "staff" permission set for that
person, nothing more: managers and the main administrator are not
affected, and individual allow / deny overrides still apply on top.

"general" keeps the original broad staff access, so accounts created
before work areas existed behave exactly as they did.
"""

from __future__ import annotations

GENERAL = "general"

# Everyone needs these to use the app and work with colleagues.
COMMON = {
    "dashboard.view",
    "settings.view",
    "branding.view",
    "chat.use",
    "meetings.use",
    "presence.view",
    "tasks.view",
    "tasks.manage",
    "groups.view",
}

MORTUARY = COMMON | {
    "cases.view",
    "mortuary.view",
    "remains.view",
    "remains.manage",
    "death_records.view",
    "death_records.manage",
    "paperwork.view",
    "paperwork.manage",
    "documents.view",
    "resources.view",
    "resource_bookings.view",
    "inventory.view",
    "inventory.stock",
    "branches.view",
}

FINANCE = COMMON | {
    "families.view",
    "families.manage",
    "members.view",
    "members.create",
    "members.edit",
    "membership_plans.view",
    "memberships.view",
    "memberships.create",
    "memberships.edit",
    "contributions.view",
    "contributions.create",
    "contributions.edit",
    "payments.view",
    "payments.create",
    "payments.edit",
    "beneficiaries.view",
    "claims.view",
    "claims.create",
    "financials.view",
    "financial_documents.view",
    "receipts.view",
    "reports.view",
    "communications.view",
    "communications.send",
    "documents.view",
    "branches.view",
}

OPERATIONS = COMMON | {
    "cases.view",
    "cases.create",
    "cases.edit",
    "families.view",
    "families.manage",
    "members.view",
    "memberships.view",
    "services.view",
    "services.manage",
    "arrangements.view",
    "arrangements.manage",
    "collections.view",
    "run_sheet.view",
    "resources.view",
    "resource_bookings.view",
    "resource_bookings.manage",
    "death_records.view",
    "paperwork.view",
    "mortuary.view",
    "remains.view",
    "documents.view",
    "documents.manage",
    "communications.view",
    "communications.send",
    "inventory.view",
    "suppliers.view",
    "branches.view",
}

WORK_AREAS: dict[str, dict] = {
    "mortuary": {
        "label": "Mortuary",
        "summary": (
            "Receives bodies, records custody, preparation and "
            "readiness. No money, memberships or finance reports."
        ),
        "permissions": MORTUARY,
    },
    "finance": {
        "label": "Finance and memberships",
        "summary": (
            "Registers members, records contributions and payments, "
            "follows arrears. No mortuary operations or full case "
            "records."
        ),
        "permissions": FINANCE,
    },
    "operations": {
        "label": "Funeral operations",
        "summary": (
            "Opens and coordinates cases, services, vehicles and "
            "schedules. No payments or finance reports."
        ),
        "permissions": OPERATIONS,
    },
}

VALID_AREAS = {GENERAL, *WORK_AREAS}


def area_permissions(area: str | None) -> set[str] | None:
    """The permissions an area grants, or None for broad staff access."""

    if not area or area == GENERAL:
        return None

    entry = WORK_AREAS.get(area)

    return set(entry["permissions"]) if entry else None


def catalogue() -> list[dict]:
    return [
        {
            "id": GENERAL,
            "label": "General staff",
            "summary": (
                "The broad staff access used before work areas "
                "existed."
            ),
        },
        *[
            {"id": key, "label": v["label"], "summary": v["summary"]}
            for key, v in WORK_AREAS.items()
        ],
    ]
