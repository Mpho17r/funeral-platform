# Job-focused roles. Each sees and does only its own part of the work;
# the permissions behind them live in services/permission_seed.py and can
# still be adjusted per person with overrides.
WORK_AREA_ROLES = {
    "mortuary",
    "finance",
    "operations",
}

# Everyone below manager level. A manager may manage these.
STAFF_LEVEL_ROLES = {
    "staff",
} | WORK_AREA_ROLES

BUSINESS_ROLES = {
    "main_admin",
    "manager",
} | STAFF_LEVEL_ROLES

MANAGEABLE_ROLES = {
    "manager",
} | STAFF_LEVEL_ROLES

ROLE_MAIN_ADMIN = "main_admin"
ROLE_MANAGER = "manager"
ROLE_STAFF = "staff"


def work_area_for(role: str) -> str:
    """Which dashboard and work a role is built around."""

    return role if role in WORK_AREA_ROLES else "general"
