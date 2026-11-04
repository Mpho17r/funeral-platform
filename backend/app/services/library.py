"""The business's document library: files on disk, expiry and alerts.

What a file really is is decided by its contents (the same rule as staff
chat), never by the name or type the browser claims.
"""

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models.appointments import BusinessDocument
from app.models.notification import Notification
from app.services import chat_files
from app.services.notifications import notify, users_with_permission

STORAGE_ROOT = Path("storage/library")
SOON_DAYS = 30

# The same everyday file types as staff chat, minus voice notes.
ALLOWED = (
    chat_files.IMAGE_TYPES
    | {"application/pdf", "text/plain", "text/csv"}
    | set(chat_files.OFFICE.values())
)


class LibraryError(ValueError):
    """The file cannot be kept; the text says why."""


def check_file(filename: str, contents: bytes) -> tuple[str, str]:
    """(clean name, media type) for an acceptable file, or LibraryError."""
    name = chat_files.clean_name(filename)
    try:
        media_type = chat_files.detect(name, contents)
    except chat_files.ChatFileError as exc:
        raise LibraryError(str(exc)) from exc
    if media_type not in ALLOWED:
        raise LibraryError(
            "Keep a picture, PDF, Word, Excel, PowerPoint, text or CSV file."
        )
    return name, media_type


def _path(business_id: UUID, doc_id: UUID) -> Path:
    return STORAGE_ROOT / str(business_id) / str(doc_id)


def save(business_id: UUID, doc_id: UUID, contents: bytes) -> None:
    path = _path(business_id, doc_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(contents)


def locate(business_id: UUID, doc_id: UUID) -> Path | None:
    path = _path(business_id, doc_id)
    return path if path.is_file() else None


def _today() -> date:
    """Today in South Africa, whatever the server's own clock says."""
    return datetime.now(ZoneInfo("Africa/Johannesburg")).date()


def expiry_state(expires_on: date | None, today: date | None = None) -> str | None:
    """"expired", "soon" (within 30 days) or None when it is fine or has none."""
    if expires_on is None:
        return None
    today = today or _today()
    if expires_on < today:
        return "expired"
    if expires_on <= today + timedelta(days=SOON_DAYS):
        return "soon"
    return None


def alert_expiring(db: Session, today: date | None = None) -> int:
    """Tell the people who manage documents about ones that are about to
    expire or have expired, at most once every 20 days per document."""
    today = today or _today()
    count = 0
    horizon = today + timedelta(days=SOON_DAYS)
    docs = (
        db.query(BusinessDocument)
        .filter(
            BusinessDocument.archived_at.is_(None),
            BusinessDocument.expires_on.is_not(None),
            BusinessDocument.expires_on <= horizon,
        )
        .all()
    )
    recent = datetime.now(timezone.utc) - timedelta(days=20)
    managers: dict[UUID, list[UUID]] = {}
    for doc in docs:
        link = f"/documents?doc={doc.id}"
        already = (
            db.query(Notification.id)
            .filter(
                Notification.business_id == doc.business_id,
                Notification.kind == "document_expiry",
                Notification.link == link,
                Notification.created_at >= recent,
            )
            .first()
        )
        if already:
            continue
        if doc.business_id not in managers:
            managers[doc.business_id] = users_with_permission(
                db, doc.business_id, "library.manage"
            )
        state = expiry_state(doc.expires_on, today)
        days = (doc.expires_on - today).days
        title = (
            f"{doc.title} has expired"
            if state == "expired"
            else f"{doc.title} expires in {days} day{'s' if days != 1 else ''}"
        )
        count += notify(
            db,
            business_id=doc.business_id,
            user_ids=managers[doc.business_id],
            kind="document_expiry",
            title=title,
            body=f"Expiry date: {doc.expires_on:%d %B %Y}",
            link=link,
        )
    db.commit()
    return count
