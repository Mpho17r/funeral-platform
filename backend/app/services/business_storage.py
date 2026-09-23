from pathlib import Path
from uuid import UUID

from fastapi import UploadFile


STORAGE_ROOT = Path("storage/branding")


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

    extension = ".png"

    if file.content_type == "image/jpeg":
        extension = ".jpg"
    elif file.content_type == "image/webp":
        extension = ".webp"

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