"""Decode and verify uploaded raster images before storing them."""

from io import BytesIO
import warnings

from PIL import Image, UnidentifiedImageError

MAX_IMAGE_PIXELS = 20_000_000
MAX_IMAGE_DIMENSION = 8_000

FORMATS = {
    "PNG": (".png", "image/png"),
    "JPEG": (".jpg", "image/jpeg"),
    "WEBP": (".webp", "image/webp"),
}


def validate_image(contents: bytes) -> tuple[str, str]:
    """Return safe extension/media type only after the image fully decodes."""
    if not contents:
        raise ValueError("The image is empty.")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)

            with Image.open(BytesIO(contents)) as image:
                image_format = image.format
                width, height = image.size

                if image_format not in FORMATS:
                    raise ValueError("Use a PNG, JPEG or WebP image file.")

                if (
                    width < 1
                    or height < 1
                    or width > MAX_IMAGE_DIMENSION
                    or height > MAX_IMAGE_DIMENSION
                    or width * height > MAX_IMAGE_PIXELS
                ):
                    raise ValueError(
                        "The image dimensions are too large. "
                        "Use an image with no more than 20 megapixels."
                    )

                image.verify()

            # verify() checks structure but does not decode all pixel data.
            # Reopen and load to ensure the pixel stream is actually readable.
            with Image.open(BytesIO(contents)) as image:
                image.load()

    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise ValueError(
            "The image file is invalid, incomplete or cannot be decoded."
        ) from exc

    return FORMATS[image_format]
