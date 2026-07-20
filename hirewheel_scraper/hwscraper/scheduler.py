"""Background scheduler: runs a scrape cycle now, then every 3 hours.

Lives entirely on its own thread and owns the Playwright Session (sync Playwright
must not touch the Tk main thread). It talks to the UI only through a thread-safe
queue of UIEvent objects — the UI polls that queue with ``root.after``.

Auth handling: launch the app *after* logging in (`python -m hwscraper.login`).
If the session later expires, the scheduler releases the browser, emits
AUTH_NEEDED, and quietly re-probes every couple of minutes so it auto-resumes
once you log in again.
"""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from . import config
from .pipeline import CycleResult, NotAuthenticated, run_cycle
from .session import Session

# How long to wait before re-checking the session after an auth failure.
_REAUTH_RETRY_SECONDS = 120


@dataclass
class UIEvent:
    """Something the scheduler wants the UI to show."""

    type: str  # "status" | "cycle" | "auth_needed" | "error"
    message: str = ""
    payload: Any = None
    at: datetime = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.at is None:
            self.at = datetime.now(timezone.utc)


class Scheduler:
    def __init__(self, interval_s: int = config.SCRAPE_INTERVAL_SECONDS):
        self.interval_s = interval_s
        self.events: "queue.Queue[UIEvent]" = queue.Queue()
        self._stop = threading.Event()
        self._run_now = threading.Event()
        self._thread: threading.Thread | None = None

    # -- public API (called from the UI/main thread) --------------------------
    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, name="hw-scraper", daemon=True)
        self._thread.start()

    def trigger_now(self) -> None:
        """Ask for an immediate cycle instead of waiting for the timer."""
        self._run_now.set()

    def stop(self) -> None:
        self._stop.set()
        self._run_now.set()  # wake the wait so the thread can exit promptly
        if self._thread is not None:
            self._thread.join(timeout=10)

    # -- internals (scheduler thread) -----------------------------------------
    def _emit(self, ev: UIEvent) -> None:
        self.events.put(ev)

    def _interruptible_wait(self, seconds: float) -> None:
        """Sleep, but wake early if stop or run-now fires."""
        self._run_now.wait(timeout=seconds)
        self._run_now.clear()

    def _loop(self) -> None:
        while not self._stop.is_set():
            authed = self._run_one_cycle()
            if self._stop.is_set():
                break
            # Full interval after a good scan; short retry while we wait to sign in.
            self._interruptible_wait(self.interval_s if authed else _REAUTH_RETRY_SECONDS)

    def _run_one_cycle(self) -> bool:
        """Open the browser, scan once, then close it. Returns True if authed.

        The browser is opened and closed around each cycle on purpose: it holds
        the persistent-profile lock only for the few seconds of scanning, leaving
        the profile free the rest of the time so the user can run
        ``python -m hwscraper.login`` if the session ever expires.
        """
        try:
            with Session(headless=True) as sess:
                if not sess.is_authenticated():
                    self._emit_auth_needed()
                    return False
                self._emit(UIEvent("status", "Scraping…"))
                result: CycleResult = run_cycle(
                    sess,
                    on_progress=lambda label: self._emit(UIEvent("status", f"Scanning {label}…")),
                )
                self._emit(UIEvent("cycle", "Cycle complete.", payload=result))
                return True
        except NotAuthenticated:
            self._emit_auth_needed()
            return False
        except Exception as exc:
            # Includes the profile being locked (e.g. a login window is open).
            self._emit(UIEvent("error", f"Browser/session error: {exc}"))
            return False

    def _emit_auth_needed(self) -> None:
        self._emit(
            UIEvent(
                "auth_needed",
                "Not signed in. Quit the app and run:  python -m hwscraper.login",
            )
        )
