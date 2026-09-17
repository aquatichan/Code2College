"""Central configuration: where things live, how often we run, and what we watch."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# --- Paths -------------------------------------------------------------------
# Everything lives under the package's parent dir (hirewheel_scraper/).
ROOT = Path(__file__).resolve().parent.parent

# The persistent Playwright browser profile. The student logs in here ONCE and
# the session is reused on every cycle. Gitignored — it holds live cookies.
PROFILE_DIR = ROOT / ".pw_profile"

# Local data: JSON snapshots, screenshots, and the run log.
DATA_DIR = ROOT / "data"
SNAPSHOT_DIR = DATA_DIR / "snapshots"
SCREENSHOT_DIR = DATA_DIR / "screenshots"

# --- Timing ------------------------------------------------------------------
SCRAPE_INTERVAL_SECONDS = 3 * 60 * 60  # every 3 hours

# Per-page load budget. Server-rendered Bootstrap pages are fast, but give slow
# connections room.
PAGE_TIMEOUT_MS = 30_000

# --- Site --------------------------------------------------------------------
BASE_URL = "https://www.hirewheel.ai"

# A protected page used purely to test whether we still have a valid session.
AUTH_PROBE_URL = f"{BASE_URL}/intern/notifications"

# The login page path fragment we get redirected to when NOT signed in.
LOGIN_URL_MARKERS = ("/login", "/accounts/login", "/sign-in")


@dataclass(frozen=True)
class Page:
    """One watched page."""

    key: str          # stable internal id, also the snapshot filename
    url: str          # full URL to fetch
    label: str        # human-friendly name for the UI


# The 11 pages a signed-in STUDENT account should scan each cycle.
PAGES: tuple[Page, ...] = (
    Page("modules", f"{BASE_URL}/learning/modules", "Learning Modules"),
    Page("internship_prep", f"{BASE_URL}/internship-prep/", "Internship Prep Projects"),
    Page("college_pathways", f"{BASE_URL}/college-pathways/", "College Pathways"),
    Page("marketplace", f"{BASE_URL}/marketplace/browse", "Marketplace"),
    Page("my_projects", f"{BASE_URL}/intern/my_projects", "My Projects"),
    Page("meetings", f"{BASE_URL}/intern/meetings", "My Interviews"),
    Page("surveys", f"{BASE_URL}/surveys/my", "My Surveys"),
    Page("program", f"{BASE_URL}/program/dashboard", "Program Hub"),
    Page("special_events", f"{BASE_URL}/special-events", "Special Events"),
    Page("notifications", f"{BASE_URL}/intern/notifications", "Notifications"),
    Page("news", f"{BASE_URL}/news/", "Newsfeed"),
)


def ensure_dirs() -> None:
    """Create the local data directories if they don't exist yet."""
    for d in (DATA_DIR, SNAPSHOT_DIR, SCREENSHOT_DIR):
        d.mkdir(parents=True, exist_ok=True)
