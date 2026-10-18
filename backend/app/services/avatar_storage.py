"""Profile photos. Kept on disk next to the other uploads, one file per
person, replaced when they change it."""

from pathlib import Path
from uuid import UUID

MAX_AVATAR_BYTES = 2 * 1024 * 1024
STORAGE_ROOT = Path("storage/avatars")

# What the file really is is decided by its first bytes, never by the
# name or content type the browser claims.
SIGNATURES = (
    (b"\x89PNG\r\n\x1a\n", ".png", "image/png"),
    (b"\xff\xd8\xff", ".jpg", "image/jpeg"),
)


class AvatarError(ValueError):
    """The uploaded photo cannot be used."""


def detect_type(contents: bytes) -> tuple[str, str]:
    for signature, extension, media_type in SIGNATURES:
        if contents.startswith(signature):
            return extension, media_type

    if contents[:4] == b"RIFF" and contents[8:12] == b"WEBP":
        return ".webp", "image/webp"

    raise AvatarError("Use a PNG, JPEG or WebP picture.")


def _folder(business_id: UUID) -> Path:
    return STORAGE_ROOT / str(business_id)


def save_avatar(business_id: UUID, user_id: UUID, contents: bytes) -> None:
    if not contents:
        raise AvatarError("The file is empty.")

    if len(contents) > MAX_AVATAR_BYTES:
        raise AvatarError("The picture is larger than 2 MB.")

    extension, _ = detect_type(contents)

    remove_avatar(business_id, user_id)

    folder = _folder(business_id)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{user_id}{extension}").write_bytes(contents)


def find_avatar(business_id: UUID, user_id: UUID) -> tuple[Path, str] | None:
    for extension, media_type in (
        (".png", "image/png"),
        (".jpg", "image/jpeg"),
        (".webp", "image/webp"),
    ):
        path = _folder(business_id) / f"{user_id}{extension}"

        if path.is_file():
            return path, media_type

    return None


def remove_avatar(business_id: UUID, user_id: UUID) -> None:
    found = find_avatar(business_id, user_id)

    while found is not None:
        found[0].unlink(missing_ok=True)
        found = find_avatar(business_id, user_id)
