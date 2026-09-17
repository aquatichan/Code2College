"""Background scan runner: scans every user on their interval, plus on demand.

Replaces the desktop project's `scheduler.py`. The loop shape is the same — run
a cycle, wait, repeat — but there is no Tk event queue: results go straight to
the database and out as a notification.

The whole runner lives on ONE thread and creates its own Playwright instance per
cycle, which keeps sync Playwright off the API's async event loop.

Auth handling differs from the desktop version too. That one re-probed a dead
session every two minutes forever; here a user whose session has expired is
simply skipped until they sign in again, and told once. Re-probing dead cookies
achieves nothing and just burns browser launches.
"""

from __future__ import annotations

import sqlite3
import threading
import traceback
from datetime import datetime, timedelta, timezone

from . import config, db, media, push
from .browser import UserBrowser
from .pipeline import NotAuthenticated, run_cycle


class ScanRunner:
    def __init__(self, tick_s: int = config.RUNNER_TICK_SECONDS):
        self.tick_s = tick_s
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._lock = threading.Lock()
        self._pending: set[str] = set()
        self._status: dict[str, str] = {}
        self._thread: threading.Thread | None = None

    # -- public API (called from the API thread) ------------------------------
    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="hw-runner", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout=30)
            self._thread = None

    def trigger(self, user_id: str) -> None:
        """Ask for an immediate scan instead of waiting for the interval."""
        with self._lock:
            self._pending.add(user_id)
        self._wake.set()

    def status_for(self, user_id: str) -> str:
        with self._lock:
            return self._status.get(user_id, "idle")

    # -- internals (runner thread) --------------------------------------------
    def _set_status(self, user_id: str, text: str) -> None:
        with self._lock:
            self._status[user_id] = text

    def _take_pending(self) -> set[str]:
        with self._lock:
            due, self._pending = self._pending, set()
            return due

    def _loop(self) -> None:
        conn = db.connect()
        try:
            while not self._stop.is_set():
                try:
                    self._tick(conn)
                except Exception:
                    traceback.print_exc()
                self._wake.wait(timeout=self.tick_s)
                self._wake.clear()
        finally:
            conn.close()

    def _tick(self, conn: sqlite3.Connection) -> None:
        manual = self._take_pending()
        for user in db.all_users(conn):
            if self._stop.is_set():
                return
            user_id = user["id"]
            forced = user_id in manual
            if not forced:
                if user["needs_reauth"]:
                    continue
                if not self._is_due(conn, user):
                    continue
            self._scan_user(conn, user_id)
        self._prune(conn)

    def _is_due(self, conn: sqlite3.Connection, user: sqlite3.Row) -> bool:
        last = db.last_scan_time(conn, user["id"])
        if last is None:
            return True
        return datetime.now(timezone.utc) - last >= timedelta(
            seconds=self._effective_interval(conn, user)
        )

    def _effective_interval(self, conn: sqlite3.Connection, user: sqlite3.Row) -> int:
        """The stored interval, but never faster than what has been paid for.

        Entitlement is also checked when the interval is set, but that is a
        point-in-time check: a refund, a revoked family-sharing purchase, or
        leftover data would otherwise keep scanning at a rate the account is no
        longer entitled to, forever. Clamping here makes the paid tier depend on
        the purchase still being valid *now*.
        """
        wanted = user["interval_seconds"] or config.SCRAPE_INTERVAL_SECONDS
        if db.interval_is_unlocked(conn, user["id"], wanted):
            return wanted
        return config.FREE_MIN_INTERVAL_SECONDS

    def _scan_user(self, conn: sqlite3.Connection, user_id: str) -> None:
        user = db.get_user(conn, user_id)
        if user is None:
            return

        state = db.load_auth_state(conn, user_id)
        scan_id = db.start_scan(conn, user_id)

        if state is None:
            db.finish_scan(conn, scan_id, status="auth_needed")
            self._flag_reauth(conn, user_id, was_flagged=bool(user["needs_reauth"]))
            return

        try:
            self._set_status(user_id, "Starting browser…")
            with UserBrowser(state) as browser:
                if not browser.is_authenticated():
                    raise NotAuthenticated(config.AUTH_PROBE_URL)

                result = run_cycle(
                    browser,
                    conn,
                    user_id,
                    scan_id,
                    on_progress=lambda label: self._set_status(user_id, f"Scanning {label}…"),
                )
                # Persist the refreshed cookies before the context goes away.
                db.save_auth_state(conn, user_id, browser.storage_state())

            db.finish_scan(conn, scan_id, status="ok", change_count=result.total_changes)
            self._set_status(user_id, "idle")
            push.notify_cycle(conn, user_id, result)

        except NotAuthenticated:
            db.finish_scan(conn, scan_id, status="auth_needed")
            self._set_status(user_id, "signed out")
            self._flag_reauth(conn, user_id, was_flagged=bool(user["needs_reauth"]))
        except Exception as exc:
            traceback.print_exc()
            db.finish_scan(conn, scan_id, status="error", error=f"{type(exc).__name__}: {exc}")
            self._set_status(user_id, "error")

    def _flag_reauth(self, conn: sqlite3.Connection, user_id: str, *, was_flagged: bool) -> None:
        db.set_needs_reauth(conn, user_id, True)
        # Only nag once per expiry, not on every attempt.
        if not was_flagged:
            push.notify_reauth(conn, user_id)

    def _prune(self, conn: sqlite3.Connection) -> None:
        """Drop old scans that recorded nothing, and their screenshots with them."""
        rows = db.prunable_scans(conn)
        if not rows:
            return
        for row in rows:
            media.delete_scan_media(row["user_id"], row["id"])
        db.delete_scans(conn, [row["id"] for row in rows])


RUNNER = ScanRunner()
