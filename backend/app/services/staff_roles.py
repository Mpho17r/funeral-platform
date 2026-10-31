"""Work out what each person does, and what a piece of work needs.

KAI looks at a person's job title and system role to decide which kinds
of work suit them, and at the wording of a task to decide what kind of
work it is. Matching the two comes before workload. Nothing here is
hidden or secret: managers can see what KAI detected for each person.
"""

import re

CATEGORIES: dict[str, tuple[str, ...]] = {
    "finance": (
        "financ", "account", "bookkeep", "cashier", "payroll", "invoice",
        "payment", "tax", "vat", "budget", "bank", "billing", "debtor",
        "creditor", "reconcil", "expense", "receipt", "salary", "salaries",
    ),
    "sales": (
        "sales", "marketing", "customer", "client", "lead", "quote",
        "social media", "advert", "promo", "campaign", "brand", "prospect",
        "follow up with", "enquir",
    ),
    "operations": (
        "operation", "logistic", "driver", "deliver", "warehouse", "stock",
        "supply", "dispatch", "procure", "purchase", "order", "vehicle",
        "fleet", "inventory", "supplier", "installation",
    ),
    "admin": (
        "admin", "secretar", "reception", "office", "clerk", "schedule",
        "filing", "document", "diary", "booking", "paperwork", "records",
    ),
    "hr": (
        "hr", "human resource", "recruit", "hiring", "leave", "staff ",
        "onboard", "training", "payslip", "contract",
    ),
    "tech": (
        "it ", "developer", "tech", "software", "website", "system",
        "computer", "network", "app ", "email setup", "password",
    ),
    "management": (
        "manager", "supervis", "director", "owner", "head of", "lead ",
        "chief", "ceo", "coordinator", "approve", "review",
    ),
    "mortuary": ("mortuary", "embalm", "prepar", "viewing", "cold room"),
}

# The system roles this platform already has.
ROLE_CATEGORY = {
    "finance": "finance",
    "operations": "operations",
    "mortuary": "mortuary",
    "manager": "management",
    "main_admin": "management",
}


def _has(text: str, word: str) -> bool:
    if word.endswith(" "):
        return re.search(rf"\b{re.escape(word.strip())}\b", text) is not None
    return word in text


def categories_in(text: str | None) -> list[str]:
    """Every category the words point to, strongest first."""

    lowered = f" {(text or '').lower()} "
    scored = []
    for name, words in CATEGORIES.items():
        hits = sum(1 for w in words if _has(lowered, w))
        if hits:
            scored.append((hits, name))
    scored.sort(key=lambda r: (-r[0], r[1]))
    return [name for _, name in scored]


def category_for_text(text: str | None) -> str:
    found = categories_in(text)
    return found[0] if found else "general"


def profile(job_title: str | None, role: str | None) -> list[str]:
    """What suits this person: from their job title first, then their role."""

    out = categories_in(job_title)
    from_role = ROLE_CATEGORY.get(role or "")
    if from_role and from_role not in out:
        out.append(from_role)
    return out


def suitability(job_title: str | None, role: str | None, wanted: str) -> int:
    """0 = no idea, 2 = their job title says so, 1 = their role says so."""

    if wanted == "general":
        return 0
    if wanted in categories_in(job_title):
        return 2
    if ROLE_CATEGORY.get(role or "") == wanted:
        return 1
    return 0
