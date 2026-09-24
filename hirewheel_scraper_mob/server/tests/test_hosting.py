"""Hosting tests: what has to hold once friends use a shared server.

* The production guard refuses laptop-only settings.
* Each device's push goes to the APNs gateway its build uses, and a token sent
  to the wrong one is retried on the other and remembered.
* The hosted-login stream is relayed over the API's own address, and only to
  whoever holds that login's key.
"""

from __future__ import annotations

import os
import socket
import sys
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_TMP = tempfile.mkdtemp(prefix="hw-hosting-test-")
# config reads these at import time, so they must be set before hwserver loads.
os.environ["HW_DATA_DIR"] = _TMP
os.environ["HW_INVITE_CODE"] = "let-me-in"
from hwserver.crypto import generate_key  # noqa: E402

os.environ["HW_SECRET_KEY"] = generate_key()

from fastapi.testclient import TestClient  # noqa: E402
from starlette.websockets import WebSocketDisconnect  # noqa: E402

from hwserver import api, authflow, config, db, push  # noqa: E402
from hwserver.apns import SendResult  # noqa: E402
from hwserver.pipeline import CycleResult  # noqa: E402


# -- production guard ---------------------------------------------------------
def test_production_guard_lists_every_unsafe_setting():
    saved = (config.INVITE_CODE, config.PUBLIC_URL, config.LOGIN_MODE)
    try:
        config.INVITE_CODE, config.PUBLIC_URL, config.LOGIN_MODE = "", "http://x:8000", "local"
        problems = " ".join(config.production_problems())
        for name in ("HW_INVITE_CODE", "HW_PUBLIC_URL", "HW_LOGIN_MODE"):
            assert name in problems, name

        config.INVITE_CODE = "code"
        config.PUBLIC_URL = "https://hirewatch.example"
        config.LOGIN_MODE = "novnc"
        assert config.production_problems() == []
    finally:
        config.INVITE_CODE, config.PUBLIC_URL, config.LOGIN_MODE = saved


# -- push environments --------------------------------------------------------
class FakeAPNs:
    """Accepts each token only on the gateway listed in ``valid``."""

    def __init__(self, valid: dict[str, str]):
        self.valid = valid
        self.calls: list[tuple[str, str]] = []

    @staticmethod
    def is_configured() -> bool:
        return True

    def send(self, token, *, title, body, data=None, collapse_id=None, environment=None):
        self.calls.append((token, environment))
        if self.valid.get(token) == environment:
            return SendResult(token, ok=True, status=200)
        return SendResult(token, ok=False, status=400, reason="BadDeviceToken")


class _Changed:
    page_key = "notifications"
    count = 2
    is_empty = False


def _cycle(scan_id: int) -> CycleResult:
    r = CycleResult(scan_id=scan_id, started_at=datetime.now(timezone.utc))
    r.diffs = [_Changed()]  # type: ignore[list-item]
    return r


def test_push_follows_each_devices_gateway_and_self_corrects():
    conn = db.connect(Path(_TMP) / "push.db")
    user = db.create_user(conn, "friend")
    debug_dev, _ = db.register_device(conn, user, push_token="tok-debug")
    tf_dev, _ = db.register_device(conn, user, push_token="tok-testflight")
    db.update_device(conn, debug_dev, push_env="sandbox")
    db.update_device(conn, tf_dev, push_env="production")
    # A third build that reported the wrong gateway (Release run from Xcode).
    odd_dev, _ = db.register_device(conn, user, push_token="tok-odd")
    db.update_device(conn, odd_dev, push_env="production")

    fake = FakeAPNs({"tok-debug": "sandbox", "tok-testflight": "production", "tok-odd": "sandbox"})
    saved = (push.CLIENT, config.PUSH_BACKEND)
    push.CLIENT, config.PUSH_BACKEND = fake, "apns"
    try:
        assert push.notify_cycle(conn, user, _cycle(1)) == 3
        assert ("tok-debug", "sandbox") in fake.calls
        assert ("tok-testflight", "production") in fake.calls
        # Wrong gateway first, then the right one...
        assert fake.calls.count(("tok-odd", "production")) == 1
        assert ("tok-odd", "sandbox") in fake.calls
        row = conn.execute("SELECT push_env, push_token FROM devices WHERE id = ?", (odd_dev,)).fetchone()
        # ...remembered, and the token is NOT retired for being on the wrong one.
        assert row["push_env"] == "sandbox" and row["push_token"] == "tok-odd"

        fake.calls.clear()
        push.notify_cycle(conn, user, _cycle(2))
        assert ("tok-odd", "production") not in fake.calls
    finally:
        push.CLIENT, config.PUSH_BACKEND = saved
        conn.close()


def test_push_env_is_validated_and_stored():
    with TestClient(api.app) as client:
        r = client.post("/enroll", json={"invite_code": "let-me-in"})
        auth = {"Authorization": f"Bearer {r.json()['device_token']}"}
        bad = client.post("/devices/push", json={"push_token": "t1", "environment": "prod"}, headers=auth)
        assert bad.status_code == 400
        ok = client.post(
            "/devices/push", json={"push_token": "t1", "environment": "production"}, headers=auth
        )
        assert ok.status_code == 200
        row = api.conn().execute("SELECT push_env FROM devices WHERE push_token = 't1'").fetchone()
        assert row["push_env"] == "production"
        # Older builds send no environment; that must still work.
        assert client.post("/devices/push", json={"push_token": "t2"}, headers=auth).status_code == 200
        assert client.get("/healthz").json() == {"ok": True}


# -- restarts -----------------------------------------------------------------
def test_restart_closes_scans_left_running():
    conn = db.connect(Path(_TMP) / "restart.db")
    user = db.create_user(conn, "friend")
    done = db.start_scan(conn, user)
    db.finish_scan(conn, done, status="ok")
    orphan = db.start_scan(conn, user)  # the process died here, mid-scan

    assert db.close_interrupted_scans(conn) == 1
    row = conn.execute("SELECT status, error, finished_at FROM scans WHERE id = ?", (orphan,)).fetchone()
    assert row["status"] == "error" and row["finished_at"]
    assert "restart" in row["error"]
    ok = conn.execute("SELECT status FROM scans WHERE id = ?", (done,)).fetchone()
    assert ok["status"] == "ok"
    conn.close()


# -- login stream relay -------------------------------------------------------
def _fake_vnc_server() -> tuple[int, threading.Event]:
    """A TCP server that greets like VNC and echoes, standing in for x11vnc."""
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    done = threading.Event()

    def serve():
        conn, _ = srv.accept()
        with conn:
            conn.sendall(b"RFB 003.008\n")
            while data := conn.recv(1024):
                conn.sendall(data.upper())
        srv.close()
        done.set()

    threading.Thread(target=serve, daemon=True).start()
    return srv.getsockname()[1], done


def test_stream_is_relayed_only_with_the_right_key():
    port, _ = _fake_vnc_server()
    authflow.MANAGER._streams["sid-1"] = (port, "right-key")
    try:
        with TestClient(api.app) as client:
            try:
                with client.websocket_connect("/auth/stream/sid-1/wrong-key") as ws:
                    ws.receive_bytes()
                raise AssertionError("a wrong key must not reach the display")
            except WebSocketDisconnect as exc:
                assert exc.code == 4404

            with client.websocket_connect("/auth/stream/sid-1/right-key") as ws:
                assert ws.receive_bytes() == b"RFB 003.008\n"
                ws.send_bytes(b"hello")
                assert ws.receive_bytes() == b"HELLO"
    finally:
        authflow.MANAGER._streams.pop("sid-1", None)


def _run_all():
    for fn in (
        test_production_guard_lists_every_unsafe_setting,
        test_push_follows_each_devices_gateway_and_self_corrects,
        test_push_env_is_validated_and_stored,
        test_restart_closes_scans_left_running,
        test_stream_is_relayed_only_with_the_right_key,
    ):
        fn()
        print(f"  ok  {fn.__name__}")
    print("\n5 tests passed.")


if __name__ == "__main__":
    _run_all()
