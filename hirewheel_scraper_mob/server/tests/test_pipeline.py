"""End-to-end pipeline test with a fake browser (no login, no network).

Verifies: first run seeds silently, a later run surfaces a genuinely new item,
every page gets a screenshot every cycle, and both scans stay in history.
"""

from __future__ import annotations

import io
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image  # noqa: E402

from hwserver import config, db, media, pipeline  # noqa: E402
from hwserver.browser import FetchResult  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "notifications.html"
NOTIF_HTML = FIXTURE.read_text(encoding="utf-8")

# A second notifications state with one extra (newer) notification.
NOTIF_HTML_PLUS = NOTIF_HTML.replace(
    '<div class="list-group">',
    '''<div class="list-group">
    <a href="#" class="notif-item" data-notif-id="1400" data-item-type="notification"
       data-action-url="/marketplace/browse">
      <div class="flex-grow-1"><p class="mb-1">A new marketplace project matched your skills</p>
        <small class="notif-time" data-ts="2026-07-20T09:00:00Z">07/20/2026</small>
        <div>Register your interest before the window closes.</div></div>
    </a>''',
)


def _png(width: int = 40, height: int = 60) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (20, 30, 40)).save(buf, "PNG")
    return buf.getvalue()


class FakeBrowser:
    """Stands in for hwserver.browser.UserBrowser; returns canned HTML."""

    def __init__(self, notif_html: str):
        self.notif_html = notif_html
        self.shots = 0

    def fetch(self, url: str) -> FetchResult:
        if url.endswith("/intern/notifications"):
            html = self.notif_html
        else:
            html = '<html><body><a href="/logout">Log out</a></body></html>'
        return FetchResult(url=url, final_url=url, html=html, authed=True)

    def screenshot_png(self) -> bytes:
        self.shots += 1
        return _png()


def _point_config_at(tmp: Path) -> None:
    config.DATA_DIR = tmp
    config.MEDIA_DIR = tmp / "media"
    config.DB_PATH = tmp / "test.db"
    media.config.MEDIA_DIR = config.MEDIA_DIR


def test_pipeline_first_run_then_change():
    with tempfile.TemporaryDirectory() as td:
        _point_config_at(Path(td))
        conn = db.connect(config.DB_PATH)
        user_id = db.create_user(conn, "test")

        # First run: seeds snapshots, reports no changes. All 11 pages have
        # extractors, so nothing is skipped.
        scan1 = db.start_scan(conn, user_id)
        b1 = FakeBrowser(NOTIF_HTML)
        r1 = pipeline.run_cycle(b1, conn, user_id, scan1)
        assert r1.total_changes == 0, r1.total_changes
        assert r1.skipped == [], r1.skipped
        assert r1.errors == {}, r1.errors
        notif_diff = next(d for d in r1.diffs if d.page_key == "notifications")
        assert notif_diff.first_run

        # Screenshots are unconditional now — the timeline must not have holes.
        assert b1.shots == len(config.PAGES), b1.shots
        assert len(r1.screenshots) == len(config.PAGES)
        db.finish_scan(conn, scan1, status="ok", change_count=r1.total_changes)

        # Second run: a brand-new notification appears → exactly one add.
        scan2 = db.start_scan(conn, user_id)
        b2 = FakeBrowser(NOTIF_HTML_PLUS)
        r2 = pipeline.run_cycle(b2, conn, user_id, scan2)
        assert r2.total_changes == 1, r2.total_changes
        nd = next(d for d in r2.diffs if d.page_key == "notifications")
        assert [i.uid for i in nd.added] == ["notification:1400"]
        db.finish_scan(conn, scan2, status="ok", change_count=r2.total_changes)

        # Both scans survive: this is the history the desktop version threw away.
        scans = db.list_scans(conn, user_id)
        assert [s["id"] for s in scans] == [scan2, scan1]

        history = db.page_history(conn, user_id, "notifications")
        assert len(history) == 2
        assert history[0]["change_count"] == 1 and history[1]["change_count"] == 0
        for row in history:
            assert media.resolve(row["screenshot_path"]).is_file()

        conn.close()


def test_extract_failure_does_not_poison_the_snapshot():
    """A page whose extractor throws must leave the last good snapshot alone,
    otherwise the next run would report every item as removed then re-added."""
    with tempfile.TemporaryDirectory() as td:
        _point_config_at(Path(td))
        conn = db.connect(config.DB_PATH)
        user_id = db.create_user(conn, "test")

        scan1 = db.start_scan(conn, user_id)
        pipeline.run_cycle(FakeBrowser(NOTIF_HTML), conn, user_id, scan1)
        good, had = db.load_latest_snapshot(conn, user_id, "notifications")
        assert had and good

        from hwcore.extractors import _REGISTRY

        original = _REGISTRY["notifications"]

        def boom(_soup):
            raise RuntimeError("selector broke")

        _REGISTRY["notifications"] = boom
        try:
            scan2 = db.start_scan(conn, user_id)
            r2 = pipeline.run_cycle(FakeBrowser(NOTIF_HTML_PLUS), conn, user_id, scan2)
            assert "notifications" in r2.errors
        finally:
            _REGISTRY["notifications"] = original

        # The failed page wrote no snapshot, so the last good one still stands.
        after, had_after = db.load_latest_snapshot(conn, user_id, "notifications")
        assert had_after
        assert [i.uid for i in after] == [i.uid for i in good]
        conn.close()


def _run_all():
    test_pipeline_first_run_then_change()
    print("  ok  test_pipeline_first_run_then_change")
    test_extract_failure_does_not_poison_the_snapshot()
    print("  ok  test_extract_failure_does_not_poison_the_snapshot")
    print("\n2 tests passed.")


if __name__ == "__main__":
    _run_all()
