"""
The groups FuneralOS keeps by itself in the staff workspace.

- One group for the whole organization: every active person is in it.
- One group per active branch: that branch's staff, plus the people who
  oversee everything (the main administrator, and managers who are not
  tied to a single branch).

Membership always follows the staff list. Calling `sync` is safe at any
time: it adds people who joined, removes people who left, moved branch or
were deactivated, and renames groups when a branch is renamed.
"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.branch import Branch
from app.models.chat import ChatConversation, ChatMessage, ChatParticipant
from app.models.user import User

ORG_KEY = "organization"
ORG_NAME = "Whole organization"
OVERSEER_ROLES = {"main_admin", "manager"}


def branch_key(branch_id) -> str:
    return f"branch:{branch_id}"


def _now():
    return datetime.now(timezone.utc)


def _ensure_group(
    db: Session, business_id: UUID, key: str, name: str, description: str
) -> ChatConversation:
    conv = (
        db.query(ChatConversation)
        .filter(
            ChatConversation.business_id == business_id,
            ChatConversation.system_key == key,
        )
        .first()
    )
    if conv is None:
        conv = ChatConversation(
            business_id=business_id,
            kind="channel",
            name=name,
            description=description,
            system_key=key,
        )
        db.add(conv)
        db.flush()
        db.add(
            ChatMessage(
                business_id=business_id,
                conversation_id=conv.id,
                sender_id=None,
                kind="system",
                body="This group is kept up to date automatically.",
                # Stamped now, before anyone is added, so nobody starts
                # with an unread message they did nothing to deserve.
                created_at=_now(),
            )
        )
    elif conv.name != name:
        conv.name = name
    return conv


def _set_members(db: Session, conv: ChatConversation, wanted: set) -> bool:
    """Make the group's people exactly `wanted`. True if anything changed."""
    seats = {
        p.user_id: p
        for p in db.query(ChatParticipant).filter(
            ChatParticipant.conversation_id == conv.id
        )
    }
    changed = False

    for user_id, seat in seats.items():
        if user_id not in wanted:
            db.delete(seat)
            changed = True

    now = _now()
    for user_id in wanted - set(seats):
        # New people start fully read, so they are not buried in old
        # unread messages.
        db.add(
            ChatParticipant(
                conversation_id=conv.id,
                user_id=user_id,
                joined_at=now,
                last_read_at=now,
            )
        )
        changed = True

    return changed


def sync(db: Session, business_id: UUID) -> None:
    """Bring the organization and branch groups in line with the staff list.

    The caller commits.
    """
    business_id = UUID(str(business_id))
    people = (
        db.query(User.id, User.role, User.branch_id)
        .filter(User.business_id == business_id, User.is_active.is_(True))
        .all()
    )
    branches = (
        db.query(Branch)
        .filter(Branch.business_id == business_id, Branch.is_active.is_(True))
        .order_by(Branch.name)
        .all()
    )

    everyone = {p.id for p in people}
    overseers = {
        p.id
        for p in people
        if p.role == "main_admin"
        or (p.role == "manager" and p.branch_id is None)
    }

    org = _ensure_group(
        db,
        business_id,
        ORG_KEY,
        ORG_NAME,
        "Everyone in the business. Announcements and questions for the whole team.",
    )
    _set_members(db, org, everyone)

    active_keys = set()
    for branch in branches:
        key = branch_key(branch.id)
        active_keys.add(key)
        group = _ensure_group(
            db,
            business_id,
            key,
            f"{branch.name} team",
            f"Everyone who works at {branch.name}.",
        )
        team = {p.id for p in people if p.branch_id == branch.id}
        _set_members(db, group, team | overseers)

    # A branch that was closed keeps its history but stops adding people.
    stale = (
        db.query(ChatConversation)
        .filter(
            ChatConversation.business_id == business_id,
            ChatConversation.system_key.like("branch:%"),
            ChatConversation.system_key.notin_(active_keys or {""}),
        )
        .all()
    )
    for group in stale:
        _set_members(db, group, set())

    db.flush()
