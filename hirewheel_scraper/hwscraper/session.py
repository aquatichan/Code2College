"""Owns the Playwright browser and the logged-in session.

Auth model: a *persistent* browser profile. The student logs in ONCE (via
`python -m hwscraper.login`), the cookies live in ``.pw_profile/``, and every
scrape cycle reuses them. No passwords are ever stored or handled by us.

Sync Playwright note: create and use a Session on a SINGLE thread (the scheduler
thread), never the Tkinter main thread — the sync API dislikes an active event
loop and isn't thread-safe.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from playwright.sync_api import sync_playwright, Playwright, BrowserContext, Page, Error

from . import config


@dataclass
class FetchResult:
    url: str
    final_url: str
    html: str
    authed: bool


def _looks_like_login(url: str) -> bool:
    return any(marker in url for marker in config.LOGIN_URL_MARKERS)


class Session:
    """A reusable logged-in browser. Use as a context manager."""

    def __init__(self, headless: bool = True):
        self.headless = headless
        self._pw: Playwright | None = None
        self._ctx: BrowserContext | None = None
        self._page: Page | None = None

    # -- lifecycle ------------------------------------------------------------
    def __enter__(self) -> "Session":
        self.start()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def start(self) -> None:
        config.PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        self._pw = sync_playwright().start()
        self._ctx = self._pw.chromium.launch_persistent_context(
            user_data_dir=str(config.PROFILE_DIR),
            headless=self.headless,
            viewport={"width": 1512, "height": 900},
        )
        self._ctx.set_default_timeout(config.PAGE_TIMEOUT_MS)
        # Reuse a single tab for all fetches.
        self._page = self._ctx.pages[0] if self._ctx.pages else self._ctx.new_page()

    def close(self) -> None:
        try:
            if self._ctx is not None:
                self._ctx.close()
        finally:
            if self._pw is not None:
                self._pw.stop()
            self._ctx = self._pw = self._page = None

    # -- navigation -----------------------------------------------------------
    def _goto(self, url: str) -> None:
        assert self._page is not None, "Session not started"
        # 'load' is enough for these server-rendered pages; avoid networkidle
        # which can hang on analytics beacons.
        self._page.goto(url, wait_until="load")

    def fetch(self, url: str) -> FetchResult:
        """Load a page and return its rendered HTML + whether we're still authed."""
        self._goto(url)
        page = self._page
        assert page is not None
        final_url = page.url
        return FetchResult(
            url=url,
            final_url=final_url,
            html=page.content(),
            authed=self._page_is_authed(final_url),
        )

    def screenshot(self, path) -> None:
        """Full-page screenshot of whatever page is currently loaded."""
        assert self._page is not None
        self._page.screenshot(path=str(path), full_page=True)

    # -- auth -----------------------------------------------------------------
    def _page_is_authed(self, final_url: str) -> bool:
        """Signed in => not on the login page AND the intern menu's Log out link
        is present. Both checks guard against the site changing one signal."""
        if _looks_like_login(final_url):
            return False
        assert self._page is not None
        try:
            return self._page.locator('a[href="/logout"]').count() > 0
        except Error:
            return False

    def is_authenticated(self) -> bool:
        """Probe a known protected page and report whether we have a live session."""
        result = self.fetch(config.AUTH_PROBE_URL)
        return result.authed

    def wait_for_login(self, timeout_s: int = 300, poll_s: float = 2.0) -> bool:
        """Interactive: park on the login page and wait for the user to sign in.

        Only meaningful with headless=False. Returns True once authenticated."""
        self._goto(config.AUTH_PROBE_URL)
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            if self._page_is_authed(self._page.url):  # type: ignore[union-attr]
                return True
            time.sleep(poll_s)
        return False
