"""Hosted interactive login.

The student signs in themselves, exactly as in the desktop tool — the difference
is that the browser lives on the server and is streamed to their phone. We never
see a password: Hirewheel's own login form is rendered by the server's browser,
the student types into it over VNC, and we only watch for the moment the session
becomes valid.

Two modes, chosen by ``HW_LOGIN_MODE``:

* ``local``  — open a headful browser window on THIS machine. For development
  and for a single user running the server on their own laptop; it is the same
  flow as the desktop project's ``python -m hwscraper.login``.
* ``novnc``  — ephemeral headful browser on a virtual X display (Xvfb), exposed
  over x11vnc and rendered by noVNC in the app's WKWebView. The API serves the
  noVNC page and relays its WebSocket to x11vnc (see ``api.login_stream``), so
  the whole login travels over the server's one HTTPS address — no extra ports
  to open on the host. The display and the browser exist only for the duration
  of the login window.

Each login runs on its own thread with its own Playwright instance, because sync
Playwright objects must not be shared across threads.
"""

from __future__ import annotations

import os
import secrets
import shutil
import socket
import subprocess
import threading
import time
from dataclasses import dataclass, field

from . import config, db, profile
from .browser import UserBrowser


class LoginUnavailable(RuntimeError):
    """Raised when the host can't support the configured login mode."""


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("", 0))
        return int(s.getsockname()[1])


@dataclass
class _Display:
    """An Xvfb display with a VNC bridge in front of it."""

    number: int
    password: str
    vnc_port: int
    procs: list[subprocess.Popen] = field(default_factory=list)

    @property
    def name(self) -> str:
        return f":{self.number}"

    def stop(self) -> None:
        for p in reversed(self.procs):
            try:
                p.terminate()
                p.wait(timeout=5)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass
        self.procs.clear()


_NOVNC_BINARIES = ("Xvfb", "x11vnc")


def novnc_web_root() -> str | None:
    """Where the noVNC page lives, or None when it isn't installed."""
    root = os.environ.get("HW_NOVNC_DIR", "/usr/share/novnc")
    return root if os.path.isfile(os.path.join(root, "vnc.html")) else None


def _start_display() -> _Display:
    missing = [b for b in _NOVNC_BINARIES if shutil.which(b) is None]
    if missing:
        raise LoginUnavailable(
            "hosted login needs " + ", ".join(missing) + " on PATH. "
            "Run the server in the provided container, or set HW_LOGIN_MODE=local "
            "to sign in with a browser window on this machine instead."
        )
    if novnc_web_root() is None:
        raise LoginUnavailable(
            "noVNC web assets not found. Install noVNC or set HW_NOVNC_DIR."
        )

    # Display numbers are a tiny shared namespace; a high random one is very
    # unlikely to collide and Xvfb fails loudly if it does.
    number = secrets.randbelow(400) + 100
    vnc_port = _free_port()
    # NOTE: x11vnc takes the password on argv, so it is briefly visible in `ps`
    # on the server. Acceptable because the VNC socket is bound to localhost and
    # the whole display is torn down within minutes; worth revisiting with
    # -passwdfile if this ever runs on a shared host.
    password = secrets.token_urlsafe(9)[:8]
    disp = _Display(number=number, password=password, vnc_port=vnc_port)

    disp.procs.append(
        subprocess.Popen(
            ["Xvfb", f":{number}", "-screen", "0", "1512x900x24", "-nolisten", "tcp"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    )
    time.sleep(1.0)  # let the display come up before anything attaches

    disp.procs.append(
        subprocess.Popen(
            [
                "x11vnc", "-display", f":{number}", "-rfbport", str(vnc_port),
                "-localhost", "-passwd", password, "-forever", "-shared", "-quiet",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    )
    time.sleep(1.0)
    return disp


class LoginManager:
    """Tracks in-flight logins. One instance per process."""

    def __init__(self) -> None:
        self._threads: dict[str, threading.Thread] = {}
        # login session id -> (x11vnc port, stream key) while a display is up.
        self._streams: dict[str, tuple[int, str]] = {}
        self._lock = threading.Lock()

    def stream_port(self, sid: str, key: str) -> int | None:
        """The VNC port behind a live login stream, if ``key`` matches it."""
        with self._lock:
            entry = self._streams.get(sid)
        if entry is None or not secrets.compare_digest(entry[1], key):
            return None
        return entry[0]

    def start(self, conn, user_id: str, device_id: str | None = None) -> tuple[str, str]:
        """Begin a login. Returns (login_session_id, url_for_the_app_to_open).

        In ``local`` mode the URL is empty — the browser opens on the server
        machine and there is nothing for the phone to render.
        """
        mode = config.LOGIN_MODE
        if mode not in ("local", "novnc"):
            raise LoginUnavailable(f"unknown HW_LOGIN_MODE: {mode!r}")

        sid = db.create_login_session(
            conn, user_id, "", config.LOGIN_TIMEOUT_SECONDS, device_id=device_id
        )
        thread = threading.Thread(
            target=self._run,
            args=(sid, user_id, device_id, mode),
            name=f"hw-login-{sid[:8]}",
            daemon=True,
        )
        with self._lock:
            self._threads[sid] = thread
        thread.start()

        # In novnc mode the worker needs a moment to publish the stream URL.
        if mode == "novnc":
            for _ in range(60):
                row = db.get_login_session(conn, sid)
                if row is None:
                    break
                if row["login_url"]:
                    return sid, row["login_url"]
                if row["status"] == "failed":
                    # The display stack never came up; report it now rather than
                    # handing the app a session it would poll forever.
                    raise LoginUnavailable(row["detail"] or "could not start the login browser")
                if row["status"] != "pending":
                    break
                time.sleep(0.25)
        return sid, ""

    # -- worker ---------------------------------------------------------------
    def _run(self, sid: str, user_id: str, device_id: str | None, mode: str) -> None:
        """Own thread, own Playwright instance, own database connection."""
        conn = db.connect()
        disp: _Display | None = None
        try:
            display_name = None
            if mode == "novnc":
                disp = _start_display()
                display_name = disp.name
                key = secrets.token_urlsafe(32)
                with self._lock:
                    self._streams[sid] = (disp.vnc_port, key)
                url = (
                    f"{config.PUBLIC_URL.rstrip('/')}/novnc/vnc.html"
                    f"?autoconnect=1&resize=scale&reconnect=1"
                    f"&path=auth/stream/{sid}/{key}&password={disp.password}"
                )
                db.set_login_url(conn, sid, url)

            with UserBrowser(headless=False, display=display_name) as browser:
                if browser.wait_for_login(timeout_s=config.LOGIN_TIMEOUT_SECONDS):
                    # Work out whose account this is *before* storing the
                    # session: signing back in with the same Hirewheel email
                    # should land on your existing history, not a new account.
                    email = profile.fetch_login_email(browser)
                    owner = db.claim_account(conn, user_id, device_id, email)
                    db.save_auth_state(conn, owner, browser.storage_state())
                    if email:
                        db.set_email(conn, owner, email)
                    db.set_login_status(conn, sid, "authenticated")
                else:
                    db.set_login_status(conn, sid, "expired", "Timed out waiting for sign-in.")
        except LoginUnavailable as exc:
            db.set_login_status(conn, sid, "failed", str(exc))
        except Exception as exc:
            db.set_login_status(conn, sid, "failed", f"{type(exc).__name__}: {exc}")
        finally:
            # Tear the streamed display down the moment we are done with it — it
            # must not outlive the login window.
            with self._lock:
                self._streams.pop(sid, None)
            if disp is not None:
                disp.stop()
            conn.close()
            with self._lock:
                self._threads.pop(sid, None)


MANAGER = LoginManager()
