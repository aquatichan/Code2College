"""Server configuration: paths, timing, the watched page list, and env settings."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

# --- Paths -------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("HW_DATA_DIR", ROOT / "data"))
MEDIA_DIR = DATA_DIR / "media"
DB_PATH = DATA_DIR / "hirewheel.db"

# --- Timing ------------------------------------------------------------------
# 24 hours is the standard cadence everyone gets.
SCRAPE_INTERVAL_SECONDS = int(os.environ.get("HW_INTERVAL_SECONDS", 24 * 60 * 60))

# Scanning more often than once a day is unlocked by a one-time purchase. The
# server is where this is enforced — the app hides the options, but hiding a
# button is not a restriction, so the API rejects them too.
FREE_MIN_INTERVAL_SECONDS = 24 * 60 * 60

# Non-consumable App Store products. Each unlocks one scan interval; buying a
# faster one implies every slower one, so a single "fastest unlocked" value is
# all that has to be stored.
PRODUCTS: dict[str, int] = {
    "com.aaronqin.HirewheelWatch.interval12h": 12 * 3600,
    "com.aaronqin.HirewheelWatch.interval6h": 6 * 3600,
    "com.aaronqin.HirewheelWatch.interval3h": 3 * 3600,
    "com.aaronqin.HirewheelWatch.interval1h": 1 * 3600,
}

# Bundle id a purchase must belong to, checked during verification so a receipt
# from some other app cannot unlock anything here.
APPSTORE_BUNDLE_ID = os.environ.get("HW_APNS_BUNDLE_ID", "com.aaronqin.HirewheelWatch")

# Apple's root CA (PEM), used to verify the certificate chain on a signed
# transaction. Download from https://www.apple.com/certificateauthority/
APPSTORE_ROOT_CA_PATH = os.environ.get("HW_APPSTORE_ROOT_CA", "")

# Escape hatch for local StoreKit testing, where transactions are signed by
# Xcode's throwaway certificate rather than Apple. Never enable in production:
# it accepts any well-formed transaction without proving Apple issued it.
ALLOW_UNVERIFIED_PURCHASES = os.environ.get("HW_ALLOW_UNVERIFIED_PURCHASES") == "1"

# Which App Store environment this server honours: "sandbox" or "production".
#
# This is a separate check from the signature, and it is not optional. Apple signs
# *sandbox* transactions with a real certificate chain, so signature verification
# alone cannot tell a free TestFlight purchase from a paid one — and TestFlight
# purchases are always sandbox and always free. A production server that skips
# this check can be unlocked for free by replaying a sandbox transaction.
APPSTORE_ENVIRONMENT = os.environ.get("HW_APPSTORE_ENVIRONMENT", "sandbox").lower()

# How often the runner wakes to see whether any user is due for a scan.
RUNNER_TICK_SECONDS = 60

# Per-page load budget. Server-rendered Bootstrap pages are fast, but give slow
# connections room.
PAGE_TIMEOUT_MS = 30_000

# --- Retention ---------------------------------------------------------------
# Scans older than this are pruned, EXCEPT ones that recorded changes — those
# are the interesting history and are kept.
RETENTION_DAYS = int(os.environ.get("HW_RETENTION_DAYS", 3))

# --- Screenshots -------------------------------------------------------------
# We now keep one screenshot per page per scan (88/day at a 3h interval) rather
# than 11 total, so each is downscaled and re-encoded before storage.
SCREENSHOT_MAX_WIDTH = 1080
SCREENSHOT_WEBP_QUALITY = 80

# --- Site --------------------------------------------------------------------
BASE_URL = "https://www.hirewheel.ai"
AUTH_PROBE_URL = f"{BASE_URL}/intern/notifications"
LOGIN_URL_MARKERS = ("/login", "/accounts/login", "/sign-in")

# --- Auth flow ---------------------------------------------------------------
# "local"  → open a headful browser on THIS machine (dev / single user).
# "novnc"  → ephemeral headful browser on a virtual display, streamed to the app.
LOGIN_MODE = os.environ.get("HW_LOGIN_MODE", "local")
LOGIN_TIMEOUT_SECONDS = int(os.environ.get("HW_LOGIN_TIMEOUT", 600))
PUBLIC_URL = os.environ.get("HW_PUBLIC_URL", "http://localhost:8000")


def _stream_base() -> str:
    """Scheme + host of PUBLIC_URL with any port stripped.

    Each hosted login opens its own websockify port, so the stream URL is built
    as `<scheme>://<host>:<that port>`. Reusing PUBLIC_URL directly would append
    a second port to one that is already there.
    """
    parsed = urlparse(PUBLIC_URL)
    host = parsed.hostname or "localhost"
    return f"{parsed.scheme or 'http'}://{host}"


# Override when the stream is reached at a different host than the API.
STREAM_BASE = os.environ.get("HW_STREAM_BASE", _stream_base())

# Gate on who may enroll. Phase 1 is single-user; this exists so the "a few
# students I know" phase is invite-only rather than open.
INVITE_CODE = os.environ.get("HW_INVITE_CODE", "")

# --- Push (APNs) -------------------------------------------------------------
# "none" → the server stores device tokens but sends nothing. This is the
#          default, and the right setting until an Apple Developer account
#          exists: the app falls back to background refresh + local
#          notifications, which needs no APNs credentials at all.
# "apns" → real remote push, signed with a .p8 auth key.
PUSH_BACKEND = os.environ.get("HW_PUSH_BACKEND", "none")

APNS_KEY_PATH = os.environ.get("HW_APNS_KEY_PATH", "")       # path to AuthKey_XXX.p8
APNS_KEY_ID = os.environ.get("HW_APNS_KEY_ID", "")           # 10-char key id
APNS_TEAM_ID = os.environ.get("HW_APNS_TEAM_ID", "")         # 10-char team id
APNS_BUNDLE_ID = os.environ.get("HW_APNS_BUNDLE_ID", "com.aaronqin.HirewheelWatch")
# "sandbox" for development builds, "production" for TestFlight / App Store.
APNS_ENVIRONMENT = os.environ.get("HW_APNS_ENVIRONMENT", "sandbox")


@dataclass(frozen=True)
class Page:
    """One watched page."""

    key: str          # stable internal id, also the snapshot key
    url: str          # full URL to fetch
    label: str        # human-friendly name for the UI


# The 11 pages a signed-in STUDENT account should scan each cycle.
PAGES: tuple[Page, ...] = (
    Page("modules", f"{BASE_URL}/learning/modules", "Learning Modules"),
    Page("internship_prep", f"{BASE_URL}/internship-prep/", "Internship Prep Projects"),
    Page("college_pathways", f"{BASE_URL}/college-pathways/", "College Pathways"),
    Page("marketplace", f"{BASE_URL}/marketplace/browse?tab=open", "Marketplace · Open"),
    Page("marketplace_examples", f"{BASE_URL}/marketplace/browse?tab=examples", "Marketplace · Examples"),
    Page("my_projects", f"{BASE_URL}/intern/my_projects", "My Projects"),
    Page("meetings", f"{BASE_URL}/intern/meetings", "My Interviews"),
    Page("surveys", f"{BASE_URL}/surveys/my", "My Surveys"),
    # The Program Hub's tabs are separate server-rendered URLs, not client-side
    # panes, so each one is genuinely a different page. Watching only the default
    # tab (as v1 did) missed five of them entirely.
    Page("program", f"{BASE_URL}/program/dashboard?tab=deliverables", "Program Hub · Deliverables"),
    Page("program_assignments", f"{BASE_URL}/program/dashboard?tab=assignments", "Program Hub · Assignments"),
    Page("program_ai_training", f"{BASE_URL}/program/dashboard?tab=summer_2026", "Program Hub · AI Training"),
    Page("program_fall", f"{BASE_URL}/program/dashboard?tab=fall_2026", "Program Hub · Fall 2026"),
    Page("program_courses", f"{BASE_URL}/program/dashboard?tab=courses", "Program Hub · Live Courses"),
    Page("program_history", f"{BASE_URL}/program/dashboard?tab=history", "Program Hub · History"),
    Page("special_events", f"{BASE_URL}/special-events", "Special Events"),
    Page("notifications", f"{BASE_URL}/intern/notifications", "Notifications"),
    Page("news", f"{BASE_URL}/news/", "Newsfeed"),
)

PAGE_LABELS: dict[str, str] = {p.key: p.label for p in PAGES}


def ensure_dirs() -> None:
    """Create the local data directories if they don't exist yet."""
    for d in (DATA_DIR, MEDIA_DIR):
        d.mkdir(parents=True, exist_ok=True)
