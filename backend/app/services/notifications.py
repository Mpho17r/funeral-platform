"""
Tell people things inside the app.

`notify` only adds rows to the caller's open transaction, so a
notification is saved if and only if the action that caused it is.
Nobody is notified about their own actions.
"""

from collections.abc import Iterable
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.user import User
from app.services.permission_service import has_permission


def notify(
    db: Session,
    *,
    business_id: UUID,
    user_ids: Iterable,
    kind: str,
    title: str,
    body: str | None = None,
    link: str | None = None,
    actor_id=None,
) -> int:
    business_id = UUID(str(business_id))
    actor = str(actor_id) if actor_id else None
    wanted = {str(u) for u in user_ids if u and str(u) != actor}
    if not wanted:
        return 0

    # Only active people in this business.
    people = (
        db.query(User.id)
        .filter(
            User.business_id == business_id,
            User.id.in_([UUID(u) for u in wanted]),
            User.is_active.is_(True),
        )
        .all()
    )
    for (person_id,) in people:
        db.add(
            Notification(
                business_id=business_id,
                user_id=person_id,
                kind=kind,
                title=title[:200],
                body=body,
                link=link,
                actor_id=UUID(actor) if actor else None,
            )
        )
    return len(people)


def users_with_permission(
    db: Session, business_id: UUID, permission_key: str
) -> list[UUID]:
    """Active people who can use a permission (main admin always can)."""
    return [
        u.id
        for u in db.query(User).filter(
            User.business_id == business_id, User.is_active.is_(True)
        )
        if has_permission(
            db, user_id=u.id, role=u.role, permission_key=permission_key
        )
    ]
