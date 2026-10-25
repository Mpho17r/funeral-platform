"""
Branch isolation, enforced where the data is read.

A person who works at one branch sees that branch's cases, members and the
money and paperwork that belong to them, and nothing from other branches.
The rule lives here, once, and is applied to every database read made for
that person's request, so lists, direct links, search, dashboards and
reports all follow it without each screen having to remember.

Who is limited: anyone with a branch assigned who does not hold the
`branches.all_access` permission (the main administrator and managers do).
A record with no branch is visible to everyone in the business.

Records follow their owner: a payment belongs to a case, a contribution to
a membership, a membership to a member, so all of them inherit the owner's
branch. Reference data (plans, suppliers, users, branches) is not limited.

Background jobs, data exports and platform code run without a scope.
"""

from uuid import UUID

from sqlalchemy import event, or_, select
from sqlalchemy.orm import Session, with_loader_criteria

from app.database import Base

ALL_BRANCHES_PERMISSION = "branches.all_access"
SESSION_KEY = "branch_scope"

# Tables that carry a branch_id but are not business data to be limited.
NOT_LIMITED = {
    "users", "branches", "businesses", "mortuary_location_branches",
}

# Records that own other records. Only links to these inherit a branch;
# links to reference data (a mortuary location, a supplier) do not.
OWNERS = {
    "funeral_cases",
    "members",
    "memberships",
    "remains_records",
    "financial_documents",
}

# These are limited by their own branch and never through a parent.
BRANCH_ROOTS = {"funeral_cases", "members"}


def scope_for(db: Session, user) -> UUID | None:
    """The one branch this person is limited to, or None for all branches."""
    from app.services.permission_service import has_permission

    if user.branch_id is None:
        return None
    if has_permission(
        db,
        user_id=user.id,
        role=user.role,
        permission_key=ALL_BRANCHES_PERMISSION,
    ):
        return None
    return user.branch_id


def set_scope(db: Session, branch_id: UUID | None) -> None:
    if branch_id is None:
        db.info.pop(SESSION_KEY, None)
    else:
        db.info[SESSION_KEY] = branch_id


def current_scope(db: Session) -> UUID | None:
    return db.info.get(SESSION_KEY)


# ------------------------------------------------------------------ the rule


def _authorised_locations(branch_id):
    """Locations a branch hosts or has been authorised to use."""
    from app.models.mortuary import (
        MortuaryLocation as Loc,
        MortuaryLocationBranch as Link,
    )

    loc, link = Loc.__table__, Link.__table__
    return select(loc.c.id).where(
        or_(
            loc.c.branch_id == branch_id,
            loc.c.id.in_(
                select(link.c.location_id).where(link.c.branch_id == branch_id)
            ),
        )
    )


def _cases_in_our_mortuary(outer, branch_id):
    """A case whose remains are kept in a location this branch uses."""
    from app.models.mortuary import RemainsRecord as Remains

    rem = Remains.__table__
    return outer("id").in_(
        select(rem.c.case_id).where(
            rem.c.current_location_id.in_(_authorised_locations(branch_id))
        )
    )


SHARED_RULES = {
    "mortuary_locations": lambda outer, b: outer("id").in_(
        _authorised_locations(b)
    ),
    "remains_records": lambda outer, b: outer("current_location_id").in_(
        _authorised_locations(b)
    ),
    "funeral_cases": _cases_in_our_mortuary,
}


def _rule(table, outer, branch_id, trail=()):
    """SQL limiting `table` to a branch, or None when it is not limited.

    `outer(name)` returns the column of the row being filtered (kept
    separate so aliased entities are filtered correctly); anything inside a
    sub-select uses plain table columns, which are never re-filtered.
    """
    if table.name in NOT_LIMITED or table.name in trail:
        return None

    parts = []

    if "branch_id" in table.c:
        parts.append(
            or_(outer("branch_id") == branch_id, outer("branch_id").is_(None))
        )

    if table.name not in BRANCH_ROOTS:
        for column in table.c:
            for fk in column.foreign_keys:
                parent = fk.column.table
                if parent.name not in OWNERS or parent.name in trail:
                    continue
                inner = _rule(
                    parent,
                    lambda name, p=parent: p.c[name],
                    branch_id,
                    trail + (table.name,),
                )
                if inner is None:
                    continue
                visible = outer(column.name).in_(
                    select(parent.c[fk.column.name]).where(inner)
                )
                if column.nullable:
                    visible = or_(outer(column.name).is_(None), visible)
                parts.append(visible)

    if not parts:
        return None
    result = parts[0]
    for extra in parts[1:]:
        result = result & extra

    # A shared mortuary: a branch also sees the locations it is
    # authorised to use, and the remains kept in them.
    if table.name in SHARED_RULES:
        result = or_(result, SHARED_RULES[table.name](outer, branch_id))
    return result


def _attribute(cls, column_name):
    """The ORM attribute for a column, even if it is named differently."""
    column = cls.__table__.c[column_name]
    return getattr(cls, cls.__mapper__.get_property_by_column(column).key)


def _limited_classes():
    classes = []
    for mapper in Base.registry.mappers:
        cls = mapper.class_
        table = getattr(cls, "__table__", None)
        if table is None:
            continue
        # Probe with a dummy id to see whether this table is limited at all.
        probe = _rule(table, lambda name, t=table: t.c[name], UUID(int=0))
        if probe is not None:
            classes.append(cls)
    return classes


_CLASSES: list | None = None


def limited_classes():
    global _CLASSES
    if _CLASSES is None:
        _CLASSES = _limited_classes()
    return _CLASSES


def _criteria(cls, branch_id):
    def build(entity):
        return _rule(
            cls.__table__,
            lambda name: _attribute(entity, name),
            branch_id,
        )

    return with_loader_criteria(cls, build, include_aliases=True)


@event.listens_for(Session, "do_orm_execute")
def _limit_reads(state):
    if not state.is_select:
        return
    branch_id = state.session.info.get(SESSION_KEY)
    if branch_id is None or state.execution_options.get("all_branches"):
        return
    state.statement = state.statement.options(
        *[_criteria(cls, branch_id) for cls in limited_classes()]
    )
