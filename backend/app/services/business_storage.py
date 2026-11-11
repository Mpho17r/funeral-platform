from pathlib import Path
from uuid import UUID, uuid4

from fastapi import UploadFile

from app.services.image_validation import validate_image


STORAGE_ROOT = Path("storage/branding")
MAX_BRANDING_BYTES = 5 * 1024 * 1024

def _detect_extension(contents: bytes) -> str:
    extension, _ = validate_image(contents)
    return extension


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

    file_path = business_storage / f"{file_type}{extension}"
    temporary_path = business_storage / f".{file_type}.{uuid4().hex}.tmp"

    try:
        temporary_path.write_bytes(contents)
        # Replace atomically so an interrupted write cannot leave a partial
        # image at the public branding path.
        temporary_path.replace(file_path)
    finally:
        temporary_path.unlink(missing_ok=True)

    # A business has one current logo and one current watermark. Remove files
    # in the other formats so retrieval cannot accidentally serve an older
    # image just because PNG is checked before JPEG/WebP.
    for old_extension in (".png", ".jpg", ".webp"):
        old_path = business_storage / f"{file_type}{old_extension}"
        if old_path != file_path:
            old_path.unlink(missing_ok=True)

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