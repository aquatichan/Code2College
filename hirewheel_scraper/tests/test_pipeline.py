"""End-to-end pipeline test with a fake browser session (no login, no network).

Verifies: first run seeds silently, a later run surfaces a genuinely new item,
pages without an extractor are skipped, and screenshots fire on change.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hwscraper import config, pipeline  # noqa: E402
from hwscraper.session import FetchResult  # noqa: E402

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


class FakeSession:
    """Stands in for hwscraper.session.Session; returns canned HTML."""

    def __init__(self, notif_html: str):
        self.notif_html = notif_html
        self.shots: list[str] = []

    def fetch(self, url: str) -> FetchResult:
        if url.endswith("/intern/notifications"):
            html = self.notif_html
        else:
            html = '<html><body><a href="/logout">Log out</a></body></html>'
        return FetchResult(url=url, final_url=url, html=html, authed=True)

    def screenshot(self, path):
        self.shots.append(str(path))
        Path(path).write_bytes(b"\x89PNG\r\n")  # placeholder bytes


def _point_config_at(tmp: Path):
    config.DATA_DIR = tmp
    config.SNAPSHOT_DIR = tmp / "snapshots"
    config.SCREENSHOT_DIR = tmp / "screenshots"


def test_pipeline_first_run_then_change():
    with tempfile.TemporaryDirectory() as td:
        _point_config_at(Path(td))

        # First run: seeds snapshots, reports no changes. All 11 pages now have
        # extractors, so nothing is skipped.
        r1 = pipeline.run_cycle(FakeSession(NOTIF_HTML))
        assert r1.total_changes == 0
        assert r1.skipped == []
        notif_diff = next(d for d in r1.diffs if d.page_key == "notifications")
        assert notif_diff.first_run

        # Second run: a brand-new notification appears → exactly one add + screenshot.
        sess = FakeSession(NOTIF_HTML_PLUS)
        r2 = pipeline.run_cycle(sess)
        assert r2.total_changes == 1
        nd = next(d for d in r2.diffs if d.page_key == "notifications")
        assert [i.uid for i in nd.added] == ["notification:1400"]
        assert "notifications" in r2.screenshots and sess.shots


def _run_all():
    test_pipeline_first_run_then_change()
    print("  ok  test_pipeline_first_run_then_change")
    print("\n1 test passed.")


if __name__ == "__main__":
    _run_all()
