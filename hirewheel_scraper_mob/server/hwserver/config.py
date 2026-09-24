"""Server configuration: paths, timing, the watched page list, and env settings."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

# --- Environment -------------------------------------------------------------
# "development" (default) is for your own laptop. "production" is the hosted
# server friends use: it refuses to start with settings that are only safe
# locally — see production_problems().
ENV = os.environ.get("HW_ENV", "development")

# --- Paths -------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("HW_DATA_DIR", ROOT / "data"))
MEDIA_DIR = DATA_DIR / "media"
DB_PATH = DATA_DIR / "hirewheel.db"

# --- Timing ------------------------------------------------------------------
# Every account scans on the same fixed cadence.
SCRAPE_INTERVAL_SECONDS = int(os.environ.get("HW_INTERVAL_SECONDS", 3 * 60 * 60))

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
# Where phones reach this server. The hosted-login stream is served from the
# same address, so one HTTPS endpoint covers everything.
PUBLIC_URL = os.environ.get("HW_PUBLIC_URL", "http://localhost:8000")

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
# ...or the key's contents directly, for hosts that store secrets as env vars
# rather than files. Used when HW_APNS_KEY_PATH is empty.
APNS_KEY = os.environ.get("HW_APNS_KEY", "").replace("\\n", "\n")
APNS_KEY_ID = os.environ.get("HW_APNS_KEY_ID", "")           # 10-char key id
APNS_TEAM_ID = os.environ.get("HW_APNS_TEAM_ID", "")         # 10-char team id
APNS_BUNDLE_ID = os.environ.get("HW_APNS_BUNDLE_ID", "com.aaronqin.hirewatch")
# Each device reports which APNs gateway its token belongs to — Debug builds
# "sandbox", TestFlight / App Store builds "production" — so one server serves
# both. This is only the fallback for devices that haven't said.
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


def production_problems() -> list[str]:
    """Settings that are fine on a laptop but unsafe on a server friends use.

    Checked at startup when HW_ENV=production; any hit stops the server rather
    than letting it run half-configured with other people's sessions in it.
    """
    problems = []
    if not os.environ.get("HW_SECRET_KEY", "").strip():
        problems.append("HW_SECRET_KEY is not set (python -m hwserver.keygen)")
    if not INVITE_CODE:
        problems.append("HW_INVITE_CODE is empty, so anyone who finds the URL could enroll")
    if urlparse(PUBLIC_URL).scheme != "https":
        problems.append(f"HW_PUBLIC_URL must be https:// (got {PUBLIC_URL!r})")
    if LOGIN_MODE != "novnc":
        problems.append("HW_LOGIN_MODE must be novnc; local opens a window nobody can see")
    return problems
