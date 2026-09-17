"""One scrape cycle: for every watched page, fetch → extract → screenshot → diff → store.

Same shape as the desktop project's pipeline, including the `NotAuthenticated`
fast-exit and the per-page error isolation that keeps one broken page from
killing a cycle. Two deliberate differences:

* Results go to the database as an appended scan, not to overwritten JSON files.
* **Every page is screenshotted every cycle**, not only changed ones. The desktop
  version captured conditionally, which is right when the screenshot is just
  decoration on a change card — but here the screenshots *are* the history, and a
  timeline with holes in it is worse than no timeline.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

from hwcore.diff import PageDiff, diff_page
from hwcore.extractors import get_extractor, parse_html

from . import children, config, db, media
from .browser import UserBrowser


class NotAuthenticated(Exception):
    """Raised when the session is no longer signed in — the user must re-login."""


@dataclass
class CycleResult:
    scan_id: int
    started_at: datetime
    diffs: list[PageDiff] = field(default_factory=list)
    screenshots: dict[str, str] = field(default_factory=dict)  # page_key -> relative path
    skipped: list[str] = field(default_factory=list)           # pages with no extractor
    errors: dict[str, str] = field(default_factory=dict)       # page_key -> message
    children_scanned: int = 0                                  # detail pages followed

    @property
    def changed_pages(self) -> list[PageDiff]:
        return [d for d in self.diffs if not d.is_empty]

    @property
    def total_changes(self) -> int:
        return sum(d.count for d in self.diffs)


def run_cycle(
    browser: UserBrowser,
    conn: sqlite3.Connection,
    user_id: str,
    scan_id: int,
    *,
    on_progress: Callable[[str], None] | None = None,
) -> CycleResult:
    """Run one full pass over all pages using an already-started browser."""
    config.ensure_dirs()
    result = CycleResult(scan_id=scan_id, started_at=datetime.now(timezone.utc))

    for page in config.PAGES:
        if on_progress:
            on_progress(page.label)

        soup = _scan_page(
            browser, conn, user_id, scan_id, result,
            key=page.key, url=page.url, label=page.label, extractor_key=page.key,
        )
        if soup is None:
            continue

        # Some listings hide their real content one level down — a newsletter's
        # text lives on its own page, not on the index. Bounded and opt-in per
        # listing; see hwserver/children.py.
        for child in children.discover(page.key, soup, config.BASE_URL):
            if on_progress:
                on_progress(child.label)
            scanned = _scan_page(
                browser, conn, user_id, scan_id, result,
                key=child.key, url=child.url, label=child.label,
                extractor_key=child.extractor, parent_key=page.key,
            )
            if scanned is not None:
                result.children_scanned += 1

    return result


def _scan_page(
    browser: UserBrowser,
    conn: sqlite3.Connection,
    user_id: str,
    scan_id: int,
    result: CycleResult,
    *,
    key: str,
    url: str,
    label: str,
    extractor_key: str,
    parent_key: str | None = None,
):
    """Fetch, extract, screenshot, diff and store one page.

    Returns the parsed soup so a listing can be mined for child links without
    fetching it twice, or None if the page could not be used.
    """
    try:
        fetched = browser.fetch(url)
    except Exception as exc:  # network/timeout — record and move on
        result.errors[key] = f"fetch failed: {exc}"
        return None

    if not fetched.authed:
        # Session died mid-cycle; no point continuing — everything is behind login.
        raise NotAuthenticated(url)

    ext = get_extractor(extractor_key)
    if ext is None:
        result.skipped.append(key)
        return None

    soup = parse_html(fetched.html)
    try:
        new_items = ext(soup)
    except Exception as exc:
        # No items means we cannot store a trustworthy snapshot: an empty one
        # would read as "everything was removed" next cycle. Skip the write so
        # the next run still diffs against the last *good* state.
        result.errors[key] = f"extract failed: {exc}"
        return soup

    shot_path: str | None = None
    try:
        shot_path = media.save_screenshot(browser.screenshot_png(), user_id, scan_id, key)
        result.screenshots[key] = shot_path
    except Exception as exc:
        # A missing image is a gap in the timeline, not a reason to lose the diff.
        result.errors[key] = f"screenshot failed: {exc}"

    old_items, had_snapshot = db.load_latest_snapshot(
        conn, user_id, key, before_scan_id=scan_id
    )
    page_diff = diff_page(key, old_items, new_items, first_run=not had_snapshot)
    result.diffs.append(page_diff)

    db.save_page_snapshot(conn, scan_id, key, new_items, shot_path)
    db.save_page_diff(conn, scan_id, page_diff)
    db.record_watched_page(conn, user_id, key, label, parent_key)
    return soup
