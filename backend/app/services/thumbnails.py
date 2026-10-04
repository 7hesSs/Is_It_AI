"""
Generates small, compressed thumbnails for scan history - NOT full copies
of uploaded media. Deliberately resized small and JPEG-compressed so each
one stays in the single-digit KB range regardless of the original file size,
keeping the SQLite database small even with thumbnails included for every
image/video scan.
"""
import base64
import io

from PIL import Image

THUMBNAIL_MAX_DIMENSION = 160
THUMBNAIL_JPEG_QUALITY = 60


def make_thumbnail_data_url(image: Image.Image) -> str:
    thumb = image.convert("RGB").copy()
    thumb.thumbnail((THUMBNAIL_MAX_DIMENSION, THUMBNAIL_MAX_DIMENSION))

    buffer = io.BytesIO()
    thumb.save(buffer, format="JPEG", quality=THUMBNAIL_JPEG_QUALITY)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")

    return f"data:image/jpeg;base64,{encoded}"
