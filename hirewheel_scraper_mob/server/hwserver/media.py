"""Screenshot storage: PNG in, downscaled WebP on disk.

The desktop version kept one PNG per page and overwrote it every cycle — 11
files, forever. Keeping history means one image per page *per scan*: 88 a day at
a 3-hour interval, ~2,600 a month. Full-page PNGs at 1512px wide are far too
heavy for that, and the phone renders them at ~400pt anyway, so each shot is
downscaled and re-encoded as WebP before it is stored.
"""

from __future__ import annotations

import io
import re
import shutil
from pathlib import Path

from PIL import Image

from . import config

# Full-page screenshots of long pages are legitimately tall; Pillow's default
# decompression-bomb guard is aimed at hostile input, not our own captures.
Image.MAX_IMAGE_PIXELS = 200_000_000


# Page keys for discovered detail pages look like "news:364". A colon is legal
# in a POSIX filename but is the classic path separator on macOS and renders as
# "/" in Finder, so keys are flattened before they touch the filesystem or a URL.
_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_name(page_key: str) -> str:
    return _UNSAFE.sub("_", page_key)


def scan_dir(user_id: str, scan_id: int) -> Path:
    return config.MEDIA_DIR / user_id / str(scan_id)


def save_screenshot(png_bytes: bytes, user_id: str, scan_id: int, page_key: str) -> str:
    """Store one capture and return its path relative to MEDIA_DIR."""
    out_dir = scan_dir(user_id, scan_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{safe_name(page_key)}.webp"

    img = Image.open(io.BytesIO(png_bytes))
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")
    if img.width > config.SCREENSHOT_MAX_WIDTH:
        ratio = config.SCREENSHOT_MAX_WIDTH / img.width
        img = img.resize(
            (config.SCREENSHOT_MAX_WIDTH, max(1, round(img.height * ratio))),
            Image.LANCZOS,
        )
    img.save(out_path, "WEBP", quality=config.SCREENSHOT_WEBP_QUALITY, method=4)

    return str(out_path.relative_to(config.MEDIA_DIR))


def resolve(relative_path: str) -> Path:
    """Absolute path for a stored screenshot, guarded against traversal."""
    full = (config.MEDIA_DIR / relative_path).resolve()
    if not full.is_relative_to(config.MEDIA_DIR.resolve()):
        raise ValueError(f"path escapes media dir: {relative_path}")
    return full


def delete_scan_media(user_id: str, scan_id: int) -> None:
    shutil.rmtree(scan_dir(user_id, scan_id), ignore_errors=True)


def delete_user_media(user_id: str) -> None:
    """Remove everything stored for a user, the directory itself included.

    Deleting scan directories one by one would leave an empty folder named with
    the user's id — residual data that "delete my account" promised to remove.
    """
    shutil.rmtree(config.MEDIA_DIR / user_id, ignore_errors=True)
