from pathlib import Path
from uuid import UUID

from fastapi import UploadFile


STORAGE_ROOT = Path("storage/branding")
MAX_BRANDING_BYTES = 5 * 1024 * 1024

_SIGNATURES = (
    (b"\x89PNG\r\n\x1a\n", ".png"),
    (b"\xff\\xd8\xff", ".jpg"),
)


def _detect_extension(contents: bytes) -> str:
    """Determine the image format from its bytes, not the browser's MIME type."""
    for signature, extension in _SIGNATURES:
        if contents.startswith(signature):
            return extension
    if len(contents) >= 12 and contents[:4] == b"RIFF" and contents[8:12] == b"WEBP":
        return ".webp"
    raise ValueError("Use a genuine PNG, JPEG or WebP image.")


def save_business_branding_file(
    business_id: UUID,
    file: UploadFile,
    contents: bytes,
    file_type: str,
) -> str:
    """
    Save a business branding image to local storage.

    Supported file types:
    - logo
    - watermark
    """

    if file_type not in {"logo", "watermark"}:
        raise ValueError(
            "Branding file type must be 'logo' or 'watermark'."
        )

    if not contents:
        raise ValueError("The image is empty.")
    if len(contents) > MAX_BRANDING_BYTES:
        raise ValueError("Branding images must be 5 MB or smaller.")

    extension = _detect_extension(contents)

    business_storage = (
        STORAGE_ROOT / str(business_id)
    )

    business_storage.mkdir(
        parents=True,
        exist_ok=True,
    )

    file_path = (
        business_storage
        / f"{file_type}{extension}"
    )

    file_path.write_bytes(contents)

    # Store an API URL in the database,
    # not the physical filesystem path.
    return (
        f"/businesses/{business_id}/branding/{file_type}"
    )


def get_business_branding_file(
    business_id: UUID,
    file_type: str,
) -> Path | None:
    """
    Find a stored branding image for a business.
    """

    if file_type not in {"logo", "watermark"}:
        return None

    business_storage = (
        STORAGE_ROOT / str(business_id)
    )

    for extension in (
        ".png",
        ".jpg",
        ".webp",
    ):
        file_path = (
            business_storage
            / f"{file_type}{extension}"
        )

        if file_path.is_file():
            return file_path

    return None