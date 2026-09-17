"""Owns a Playwright browser driven by a stored, per-user session.

Rewrite of the desktop project's `session.py`. That version used
`launch_persistent_context` against one shared profile directory on disk, which
works for exactly one user on one machine. Here each user's session lives in the
database as a Playwright *storage state* (cookies + localStorage) and is loaded
into a fresh context per cycle, so one server can watch several accounts.

The auth checks are carried over unchanged — they were already correct.

Sync Playwright note: a UserBrowser must be created AND used on a single thread,
and never on a thread running an asyncio loop. The scan runner and each login
flow therefore get their own instance on their own thread.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

from playwright.sync_api import BrowserContext, Error, Page, Playwright, sync_playwright

from . import config


@dataclass
class FetchResult:
    url: str
    final_url: str
    html: str
    authed: bool


def _looks_like_login(url: str) -> bool:
    return any(marker in url for marker in config.LOGIN_URL_MARKERS)


_CAPTURE_CSS = """
*, *::before, *::after {
    animation-duration: 0s !important;
    animation-delay: 0s !important;
    transition-duration: 0s !important;
    transition-delay: 0s !important;
    scroll-behavior: auto !important;
}
/* Reveal-on-scroll wrappers sit at opacity 0 until their observer fires. */
[class*="fade"], [class*="reveal"], [class*="animate"], [class*="skeleton"],
[data-aos], [data-animate] {
    opacity: 1 !important;
    transform: none !important;
    visibility: visible !important;
    filter: none !important;
}
"""


def _debug() -> bool:
    """Set HW_DEBUG_LOGIN=1 to trace why a sign-in is or isn't being detected."""
    return os.environ.get("HW_DEBUG_LOGIN") == "1"


class UserBrowser:
    """A browser carrying one user's Hirewheel session. Use as a context manager."""

    def __init__(
        self,
        storage_state: dict[str, Any] | None = None,
        *,
        headless: bool = True,
        display: str | None = None,
    ):
        self.headless = headless
        # X display for headful runs on a virtual screen (the hosted login flow).
        self.display = display
        self._initial_state = storage_state
        self._pw: Playwright | None = None
        self._browser = None
        self._ctx: BrowserContext | None = None
        self._page: Page | None = None

    # -- lifecycle ------------------------------------------------------------
    def __enter__(self) -> "UserBrowser":
        self.start()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def start(self) -> None:
        self._pw = sync_playwright().start()
        launch_env = {**os.environ, "DISPLAY": self.display} if self.display else None
        self._browser = self._pw.chromium.launch(headless=self.headless, env=launch_env)
        self._ctx = self._browser.new_context(
            storage_state=self._initial_state,
            viewport={"width": 1512, "height": 900},
        )
        self._ctx.set_default_timeout(config.PAGE_TIMEOUT_MS)
        self._page = self._ctx.new_page()

    def close(self) -> None:
        try:
            if self._ctx is not None:
                self._ctx.close()
            if self._browser is not None:
                self._browser.close()
        finally:
            if self._pw is not None:
                self._pw.stop()
            self._pw = self._browser = self._ctx = self._page = None

    # -- session state --------------------------------------------------------
    def storage_state(self) -> dict[str, Any]:
        """Current cookies + localStorage, to be written back after every cycle.

        Hirewheel rotates its session cookie, so discarding the refreshed state
        is the most likely cause of a session that "randomly" expires early.
        """
        assert self._ctx is not None, "Browser not started"
        return self._ctx.storage_state()

    # -- navigation -----------------------------------------------------------
    def _goto(self, url: str) -> None:
        assert self._page is not None, "Browser not started"
        # 'load' is enough for these server-rendered pages; avoid networkidle
        # which can hang on analytics beacons.
        self._page.goto(url, wait_until="load")

    def fetch(self, url: str) -> FetchResult:
        """Load a page and return its rendered HTML + whether we're still authed."""
        self._goto(url)
        page = self._page
        assert page is not None
        self._reveal_hidden_content()
        final_url = page.url
        return FetchResult(
            url=url,
            final_url=final_url,
            html=page.content(),
            authed=self._page_is_authed(final_url),
        )

    def _reveal_hidden_content(self) -> None:
        """Open client-side tabs and collapsed containers before reading the page.

        Some content sits in the DOM but is hidden by CSS — inactive Bootstrap
        tab panes (Special Events' "Past Events"), collapsed accordions, and the
        module list's "Expand All" sections. Extractors that select by class can
        already reach it, but anything driven by visibility cannot, and a
        screenshot of a collapsed page shows none of it.

        Server-rendered `?tab=` URLs are a different thing entirely and are
        watched as their own pages; this only handles what one page is hiding.

        Best-effort throughout: revealing nothing is far better than failing the
        fetch. The site's own navbar toggle is deliberately left alone — expanding
        the mobile menu adds chrome to every screenshot and no information.
        """
        page = self._page
        assert page is not None

        # Prefer the page's own control when it offers one, since it may do more
        # than flip a class.
        try:
            expand = page.locator("#hw-expand-all")
            if expand.count() > 0:
                expand.first.click(timeout=2_000)
                page.wait_for_timeout(200)
        except Error:
            pass

        try:
            page.evaluate(
                """() => {
                    // Inactive tab panes: show them stacked rather than hidden.
                    document.querySelectorAll('.tab-pane').forEach(el => {
                        el.classList.add('show', 'active');
                    });
                    // Collapsed accordions, except the site's mobile nav menu.
                    document.querySelectorAll('.collapse').forEach(el => {
                        if (el.id === 'navbarNav') return;
                        if (el.closest('nav, .navbar')) return;
                        el.classList.add('show');
                        el.style.height = 'auto';
                    });
                    // Anything still explicitly hidden inside the main content.
                    const main = document.querySelector('main') || document.body;
                    main.querySelectorAll('[hidden]').forEach(el => el.removeAttribute('hidden'));
                }"""
            )
            page.wait_for_timeout(250)
        except Error:
            pass

    def screenshot_png(self) -> bytes:
        """Full-page screenshot of whatever page is currently loaded, as PNG bytes."""
        assert self._page is not None
        self._settle_for_capture()
        return self._page.screenshot(full_page=True)

    def _settle_for_capture(self) -> None:
        """Get the page visually finished before we photograph it.

        `wait_until="load"` is enough to have the markup — which is why extraction
        works — but Hirewheel reveals its cards with CSS transitions and loads
        images lazily, so a screenshot taken at that moment catches a page full of
        blank skeletons. The stored screenshots *are* the history, so capturing
        them half-rendered defeats the point of keeping them.

        Every step is best-effort: a screenshot that is merely imperfect is much
        better than one that fails and leaves a hole in the timeline.
        """
        page = self._page
        assert page is not None

        # Give in-flight requests a moment, but never hang on a chatty analytics
        # beacon the way an unbounded networkidle wait can.
        try:
            page.wait_for_load_state("networkidle", timeout=5_000)
        except Error:
            pass

        # Walk the full height so lazy images and reveal-on-scroll observers fire,
        # then return to the top for the capture.
        try:
            page.evaluate(
                """async () => {
                    const step = Math.max(200, window.innerHeight);
                    const total = document.body.scrollHeight;
                    for (let y = 0; y < total; y += step) {
                        window.scrollTo(0, y);
                        await new Promise(r => setTimeout(r, 80));
                    }
                    window.scrollTo(0, 0);
                    await new Promise(r => setTimeout(r, 150));
                }"""
            )
        except Error:
            pass

        # Neutralise animations and force anything still mid-reveal to its final
        # state, so the capture doesn't freeze a transition part-way.
        try:
            page.add_style_tag(content=_CAPTURE_CSS)
        except Error:
            pass

        # Web fonts swapping in after the shot would otherwise show as blank text.
        try:
            page.evaluate("() => document.fonts && document.fonts.ready")
        except Error:
            pass

        try:
            page.wait_for_timeout(250)
        except Error:
            pass

    # -- auth -----------------------------------------------------------------
    def _page_is_authed(self, final_url: str) -> bool:
        """Signed in => a protected page rendered instead of the login form.

        Hirewheel bounces unauthenticated requests to ``/login?next=...``, so not
        being redirected is the whole signal.

        Two richer checks have already been tried and removed. Requiring an
        ``a[href="/logout"]`` element (inherited from the desktop version) matched
        nothing on the real site, so every session read as signed out and sign-in
        could never complete. Requiring the absence of a password field then
        misfired on /account, which legitimately contains a change-password form
        while fully authenticated. Both were guesses about markup; the redirect is
        a contract the server actually keeps. Do not add a DOM check here without
        confirming it against live pages first.
        """
        return not _looks_like_login(final_url)

    def session_is_live(self) -> bool:
        """Ask the cookie jar, not the visible page, whether we are signed in.

        `context.request` shares cookie storage with the browser context, so this
        fetches the protected page exactly as the browser would — and reports
        whether the server served it or bounced us to the login form.

        This is deliberately *not* a check on the page the user is looking at:

        * It cannot be fooled by whatever is on screen mid-login, and needs no
          guesses about the site's markup (the previous DOM-based checks looked
          for a logout link, then for a password field — both guesses).
        * It sees the session no matter which tab, window or redirect the person
          finished in, because cookies are per-context, not per-page.
        * It never navigates the visible tab, so it cannot wipe a half-typed
          password while polling.
        """
        if self._ctx is None:
            return False
        try:
            response = self._ctx.request.get(config.AUTH_PROBE_URL, timeout=15_000)
        except Error as exc:
            if _debug():
                print(f"[login] probe failed: {exc}")
            return False

        landed_on_login = _looks_like_login(response.url)
        if _debug():
            print(f"[login] probe -> {response.status} {response.url} "
                  f"(login page: {landed_on_login})")
        return response.ok and not landed_on_login

    def is_authenticated(self) -> bool:
        """Probe a known protected page and report whether we have a live session."""
        return self.session_is_live()

    def wait_for_login(self, timeout_s: int = 300, poll_s: float = 2.0) -> bool:
        """Park on the login page and wait for a human to sign in.

        Only meaningful with headless=False. Returns True once authenticated."""
        self._goto(config.AUTH_PROBE_URL)
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            if self.session_is_live():
                return True
            time.sleep(poll_s)
        if _debug():
            print(f"[login] gave up after {timeout_s}s without a live session")
        return False
