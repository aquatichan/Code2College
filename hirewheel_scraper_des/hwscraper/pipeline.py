"""One scrape cycle: for every watched page, fetch → extract → diff → persist."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

from . import config, store
from .diff import PageDiff, diff_page
from .extractors import get_extractor, parse_html
from .session import Session


class NotAuthenticated(Exception):
    """Raised when the session is no longer signed in — the user must re-login."""


@dataclass
class CycleResult:
    started_at: datetime
    diffs: list[PageDiff] = field(default_factory=list)
    screenshots: dict[str, str] = field(default_factory=dict)  # page_key -> path
    skipped: list[str] = field(default_factory=list)           # pages with no extractor
    errors: dict[str, str] = field(default_factory=dict)       # page_key -> message

    @property
    def changed_pages(self) -> list[PageDiff]:
        return [d for d in self.diffs if not d.is_empty]

    @property
    def total_changes(self) -> int:
        return sum(d.count for d in self.diffs)


def run_cycle(
    session: Session,
    *,
    take_screenshots: bool = True,
    on_progress: Callable[[str], None] | None = None,
) -> CycleResult:
    """Run one full pass over all pages using an already-started Session."""
    config.ensure_dirs()
    result = CycleResult(started_at=datetime.now(timezone.utc))

    for page in config.PAGES:
        if on_progress:
            on_progress(page.label)
        try:
            fetched = session.fetch(page.url)
        except Exception as exc:  # network/timeout — record and move on
            result.errors[page.key] = f"fetch failed: {exc}"
            continue

        if not fetched.authed:
            # Session died mid-cycle; no point continuing — everything is behind login.
            raise NotAuthenticated(page.url)

        ext = get_extractor(page.key)
        if ext is None:
            result.skipped.append(page.key)
            continue

        try:
            new_items = ext(parse_html(fetched.html))
        except Exception as exc:
            result.errors[page.key] = f"extract failed: {exc}"
            continue

        first_run = not store.has_snapshot(page.key)
        old_items = store.load_snapshot(page.key)
        page_diff = diff_page(page.key, old_items, new_items, first_run=first_run)
        result.diffs.append(page_diff)
        store.save_snapshot(page.key, new_items)

        if take_screenshots and not page_diff.is_empty:
            shot = config.SCREENSHOT_DIR / f"{page.key}.png"
            try:
                session.screenshot(shot)
                result.screenshots[page.key] = str(shot)
            except Exception as exc:
                result.errors[page.key] = f"screenshot failed: {exc}"

    return result
