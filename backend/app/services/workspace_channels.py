"""
The workspace's automatic channels.

- One channel for the whole organisation: every active person is in it,
  so any announcement or question can reach everyone.
- One channel per branch (when the business has more than one active
  branch): the people who work at that branch.
- The main administrator and managers oversee everything, so they are in
  every branch channel too.

`sync` makes the channels match the team exactly and can be run any time;
it adds who is missing and removes who no longer belongs (someone who
moves branch or is deactivated loses the old branch's channel at once).
The caller commits.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.branch import Branch
from app.models.chat import ChatConversation, ChatParticipant
from app.models.user import User

ORG_KEY = "org"
OVERSIGHT_ROLES = {"main_admin", "manager"}


def branch_key(branch_id) -> str:
    return f"branch:{branch_id}"


def _now():
    return datetime.now(timezone.utc)


def sync(db: Session, business_id: UUID) -> bool:
    """Bring the automatic channels in line with the team. True if changed."""
    business_id = UUID(str(business_id))
    changed = False

    people = (
        db.query(User.id, User.branch_id, User.role)
        .filter(User.business_id == business_id, User.is_active.is_(True))
        .all()
    )
    everyone = {p.id for p in people}
    oversight = {p.id for p in people if p.role in OVERSIGHT_ROLES}

    branches = (
        db.query(Branch)
        .filter(Branch.business_id == business_id)
        .order_by(Branch.name)
        .all()
    )
    active_branches = [b for b in branches if b.is_active]

    wanted: dict[str, dict] = {
        ORG_KEY: {
            "name": "Whole organisation",
            "description": "Everyone in the business. Announcements and "
            "questions for all branches.",
            "members": everyone,
        }
    }
    # A single branch would only repeat the organisation channel.
    if len(active_branches) >= 2:
        for b in active_branches:
            staff = {p.id for p in people if p.branch_id == b.id}
            wanted[branch_key(b.id)] = {
                "name": b.name,
                "description": f"The {b.name} team.",
                "members": staff | oversight,
            }

    existing = {
        c.system_key: c
        for c in db.query(ChatConversation).filter(
            ChatConversation.business_id == business_id,
            ChatConversation.system_key.is_not(None),
        )
    }

    for key, spec in wanted.items():
        conv = existing.get(key)
        if conv is None:
            conv = ChatConversation(
                business_id=business_id,
                kind="channel",
                last_message_at=_now() - timedelta(minutes=1),
                name=spec["name"],
                description=spec["description"],
                system_key=key,
            )
            db.add(conv)
            db.flush()
            changed = True
        elif conv.name != spec["name"]:
            conv.name = spec["name"]
            conv.description = spec["description"]
            changed = True

        current = {
            p.user_id: p
            for p in db.query(ChatParticipant).filter(
                ChatParticipant.conversation_id == conv.id
            )
        }
        for uid in spec["members"] - set(current):
            db.add(
                ChatParticipant(
                    conversation_id=conv.id,
                    user_id=uid,
                    joined_at=_now(),
                    last_read_at=_now(),
                )
            )
            changed = True
        for uid, seat in current.items():
            if uid not in spec["members"]:
                db.delete(seat)
                changed = True

    # A branch that closed (or the business went down to one branch):
    # only people who oversee keep the old channel, as history.
    for key, conv in existing.items():
        if key in wanted:
            continue
        for seat in db.query(ChatParticipant).filter(
            ChatParticipant.conversation_id == conv.id
        ):
            if seat.user_id not in oversight:
                db.delete(seat)
                changed = True

    if changed:
        db.flush()
    return changed


# ---------------------------------------------------------------------
# Keep the channels in step automatically.
#
# Whenever a person or a branch is added, removed, renamed, moved,
# activated, deactivated or given another role, the channels are
# re-synced inside the same transaction. Nothing has to remember to call
# `sync`, and access to a branch channel is withdrawn the moment someone
# leaves the branch.
# ---------------------------------------------------------------------

from sqlalchemy import event, inspect as sa_inspect  # noqa: E402
from sqlalchemy.orm import Session as _Session  # noqa: E402

_WATCHED = {
    User: ("is_active", "branch_id", "role", "business_id"),
    Branch: ("is_active", "name", "business_id"),
}


def _relevant(obj, *, is_new: bool) -> bool:
    fields = _WATCHED.get(type(obj))
    if fields is None:
        return False
    if is_new:
        return True
    state = sa_inspect(obj)
    return any(state.attrs[f].history.has_changes() for f in fields)


@event.listens_for(_Session, "before_flush")
def _remember_changes(session, flush_context, instances):
    for obj in session.new:
        if _relevant(obj, is_new=True) and obj.business_id:
            session.info.setdefault("workspace_dirty", set()).add(
                obj.business_id
            )
    for obj in session.dirty:
        if _relevant(obj, is_new=False) and obj.business_id:
            session.info.setdefault("workspace_dirty", set()).add(
                obj.business_id
            )
    for obj in session.deleted:
        if type(obj) in _WATCHED and obj.business_id:
            session.info.setdefault("workspace_dirty", set()).add(
                obj.business_id
            )


@event.listens_for(_Session, "before_commit")
def _sync_before_commit(session):
    dirty = session.info.pop("workspace_dirty", None)
    if not dirty:
        return
    for business_id in dirty:
        sync(session, business_id)


@event.listens_for(_Session, "after_rollback")
def _forget_on_rollback(session):
    session.info.pop("workspace_dirty", None)
