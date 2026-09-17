"""API integration test: enroll, seed a scan, then read it back the way the app will.

Runs the real FastAPI app (including the background runner's lifespan) against a
temp data dir, with a fake browser standing in for Playwright.
"""

from __future__ import annotations

import io
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_TMP = tempfile.mkdtemp(prefix="hw-api-test-")
# config reads these at import time, so they must be set before hwserver loads.
os.environ["HW_DATA_DIR"] = _TMP
os.environ["HW_INVITE_CODE"] = "let-me-in"
from hwserver.crypto import generate_key  # noqa: E402

os.environ["HW_SECRET_KEY"] = generate_key()

from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from hwserver import api, config, db, pipeline  # noqa: E402
from hwserver.browser import FetchResult  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "notifications.html"
NOTIF_HTML = FIXTURE.read_text(encoding="utf-8")


class FakeBrowser:
    def fetch(self, url: str) -> FetchResult:
        html = (
            NOTIF_HTML
            if url.endswith("/intern/notifications")
            else '<html><body><a href="/logout">Log out</a></body></html>'
        )
        return FetchResult(url=url, final_url=url, html=html, authed=True)

    def screenshot_png(self) -> bytes:
        buf = io.BytesIO()
        Image.new("RGB", (60, 90), (30, 40, 50)).save(buf, "PNG")
        return buf.getvalue()


def test_api_end_to_end():
    with TestClient(api.app) as client:
        # Enrollment is gated by the invite code.
        assert client.post("/enroll", json={"label": "aaron"}).status_code == 403

        r = client.post("/enroll", json={"label": "aaron", "invite_code": "let-me-in"})
        assert r.status_code == 200, r.text
        enrolled = r.json()
        user_id = enrolled["user_id"]
        auth = {"Authorization": f"Bearer {enrolled['device_token']}"}

        # Unauthenticated and wrong-token requests are both rejected.
        assert client.get("/me").status_code == 401
        assert client.get("/me", headers={"Authorization": "Bearer nope"}).status_code == 401

        me = client.get("/me", headers=auth).json()
        assert me["user_id"] == user_id
        assert me["needs_reauth"] is True  # never signed in yet
        # No Apple account configured, so the app must run its own fallback.
        assert me["remote_push"] is False
        assert len(client.get("/pages", headers=auth).json()) == len(config.PAGES)

        # The app registers an APNs device token even when push is off.
        assert client.post("/devices/push", json={"push_token": "a" * 64}, headers=auth).json() == {
            "status": "ok",
            "remote_push": False,
        }

        # Seed a real scan through the pipeline, sharing the app's connection.
        conn = api.conn()
        scan_id = db.start_scan(conn, user_id)
        result = pipeline.run_cycle(FakeBrowser(), conn, user_id, scan_id)
        db.finish_scan(conn, scan_id, status="ok", change_count=result.total_changes)

        scans = client.get("/scans", headers=auth).json()
        assert [s["id"] for s in scans] == [scan_id]

        detail = client.get(f"/scans/{scan_id}", headers=auth).json()
        assert len(detail["pages"]) == len(config.PAGES)
        notif = next(p for p in detail["pages"] if p["page_key"] == "notifications")
        assert notif["label"] == "Notifications"
        assert notif["first_run"] is True
        assert notif["screenshot_path"]

        history = client.get("/pages/notifications/history", headers=auth).json()
        assert len(history) == 1
        snap = client.get(f"/snapshots/{history[0]['snapshot_id']}", headers=auth).json()
        assert snap["items"], "snapshot should carry the extracted notifications"

        # Screenshots are served, and only to their owner.
        path = history[0]["screenshot_path"]
        img = client.get(f"/media/{path}", headers=auth)
        assert img.status_code == 200 and img.headers["content-type"] == "image/webp"
        assert (
            client.get(f"/media/someone-else/{scan_id}/notifications.webp", headers=auth).status_code
            == 403
        )
        assert client.get(f"/media/{user_id}/../../etc/passwd", headers=auth).status_code in (400, 404)

        # Settings round trip.
        assert client.patch("/devices/me", json={"muted_pages": ["nope"]}, headers=auth).status_code == 400
        muted = client.patch("/devices/me", json={"muted_pages": ["news"]}, headers=auth).json()
        assert muted["muted_pages"] == ["news"]
        assert client.get("/me", headers=auth).json()["muted_pages"] == ["news"]
        assert client.patch("/me/interval", json={"interval_seconds": 60}, headers=auth).status_code == 400

        # 24h is the standard interval and always allowed.
        day = 24 * 3600
        assert client.patch(
            "/me/interval", json={"interval_seconds": day}, headers=auth
        ).json() == {"interval_seconds": day}

        # Everything faster is a paid feature. The app hides these, but hiding a
        # button isn't a restriction — the API has to refuse them too.
        for seconds in (3600, 3 * 3600, 6 * 3600, 12 * 3600):
            resp = client.patch("/me/interval", json={"interval_seconds": seconds}, headers=auth)
            assert resp.status_code == 402, f"{seconds}s should need payment, got {resp.status_code}"

        # ...and become allowed once the matching purchase is recorded.
        db.record_purchase(
            api.conn(),
            user_id,
            product_id="com.aaronqin.HirewheelWatch.interval6h",
            original_transaction_id="2000000001",
            interval_seconds=6 * 3600,
            purchased_at="2026-01-01T00:00:00+00:00",
            signature_verified=True,
            revoked=False,
        )
        assert client.patch(
            "/me/interval", json={"interval_seconds": 6 * 3600}, headers=auth
        ).json() == {"interval_seconds": 6 * 3600}

        # Purchases are independent: 6h unlocks 6h and nothing else — not the
        # faster tiers, and not the slower paid one either.
        for other in (3600, 3 * 3600, 12 * 3600):
            assert client.patch(
                "/me/interval", json={"interval_seconds": other}, headers=auth
            ).status_code == 402, f"{other}s should still be locked"

        owned = client.get("/purchases", headers=auth).json()
        assert owned["unlocked_interval_seconds"] == [6 * 3600, day]
        assert owned["purchases"][0]["product_id"].endswith("interval6h")

        # A refund gives the entitlement back.
        db.record_purchase(
            api.conn(),
            user_id,
            product_id="com.aaronqin.HirewheelWatch.interval6h",
            original_transaction_id="2000000001",
            interval_seconds=6 * 3600,
            purchased_at="2026-01-01T00:00:00+00:00",
            signature_verified=True,
            revoked=True,
        )
        assert client.get("/me", headers=auth).json()["unlocked_interval_seconds"] == [day]

        # Garbage never becomes an entitlement.
        assert client.post("/purchases", json={"jws": "not-a-token"}, headers=auth).status_code == 400

        db.set_interval(api.conn(), user_id, None)

        profile = client.get("/me", headers=auth).json()
        assert profile["free_min_interval_seconds"] == day
        assert len(profile["products"]) == 4
        assert "email" in profile

        assert client.post("/scan-now", headers=auth).json() == {"status": "queued"}

        # Erasure removes the account and its media.
        assert client.delete("/me", headers=auth).json() == {"status": "deleted"}
        assert client.get("/me", headers=auth).status_code == 401
        assert not (config.MEDIA_DIR / user_id).exists()


def _run_all():
    test_api_end_to_end()
    print("  ok  test_api_end_to_end")
    print("\n1 test passed.")


if __name__ == "__main__":
    _run_all()
