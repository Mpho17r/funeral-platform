"""Files shared in staff chat, kept on disk, one file per attachment.

What a file really is is decided by its contents, never by the name or
content type the browser claims. Only a short list of everyday types is
accepted, and anything that is not an image is always downloaded rather
than opened in the browser."""

from pathlib import Path
from uuid import UUID

MAX_BYTES = 10 * 1024 * 1024
MAX_PER_MESSAGE = 5
STORAGE_ROOT = Path("storage/chat")

IMAGE_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}

OFFICE = {
    ".docx": "application/vnd.openxmlformats-officedocument."
    "wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument."
    "spreadsheetml.sheet",
    ".pptx": "application/vnd.openxmlformats-officedocument."
    "presentationml.presentation",
}
TEXT = {".txt": "text/plain", ".csv": "text/csv"}


class ChatFileError(ValueError):
    """The file cannot be shared."""


def clean_name(name: str | None) -> str:
    base = (name or "file").replace("\\", "/").split("/")[-1]
    base = "".join(c for c in base if c.isprintable() and c not in '<>:"|?*')
    base = base.strip(" .") or "file"

    return base[:150]


def detect(filename: str, contents: bytes) -> str:
    """The media type of an acceptable file, or ChatFileError."""

    if not contents:
        raise ChatFileError("The file is empty.")

    if len(contents) > MAX_BYTES:
        raise ChatFileError("Files can be up to 10 MB.")

    if contents.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if contents.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if contents[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if contents[:4] == b"RIFF" and contents[8:12] == b"WEBP":
        return "image/webp"
    if contents.startswith(b"%PDF-"):
        return "application/pdf"

    extension = Path(filename).suffix.lower()

    if extension in OFFICE and contents.startswith(b"PK\x03\x04"):
        return OFFICE[extension]

    if extension in TEXT and b"\x00" not in contents:
        try:
            contents.decode("utf-8")
            return TEXT[extension]
        except UnicodeDecodeError:
            pass

    raise ChatFileError(
        "Share a picture, PDF, Word, Excel, PowerPoint, text or CSV file."
    )


def _path(business_id: UUID, attachment_id: UUID) -> Path:
    return STORAGE_ROOT / str(business_id) / str(attachment_id)


def save(business_id: UUID, attachment_id: UUID, contents: bytes) -> None:
    path = _path(business_id, attachment_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(contents)


def locate(business_id: UUID, attachment_id: UUID) -> Path | None:
    path = _path(business_id, attachment_id)

    return path if path.is_file() else None


def remove(business_id: UUID, attachment_id: UUID) -> None:
    _path(business_id, attachment_id).unlink(missing_ok=True)
