"""Storage-layer tests: history accumulates, diffs survive a round trip, and
session state is encrypted at rest."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hwserver.crypto import generate_key  # noqa: E402

# Must exist before any auth_state call; a per-run key is fine for tests.
os.environ["HW_SECRET_KEY"] = generate_key()

from hwcore.diff import diff_page  # noqa: E402
from hwcore.models import Item  # noqa: E402
from hwserver import config, db  # noqa: E402


def _items(*titles: str) -> list[Item]:
    return [Item.from_fields("notification", t, uid=f"notification:{t}") for t in titles]


def _fresh(td: str):
    config.DB_PATH = Path(td) / "test.db"
    conn = db.connect(config.DB_PATH)
    return conn, db.create_user(conn, "test")


def test_snapshots_accumulate_and_first_run_seeds():
    with tempfile.TemporaryDirectory() as td:
        conn, user_id = _fresh(td)

        # Run 1 — nothing stored yet, so this is a silent seed.
        scan1 = db.start_scan(conn, user_id)
        old, had = db.load_latest_snapshot(conn, user_id, "notifications", before_scan_id=scan1)
        assert (old, had) == ([], False)
        d1 = diff_page("notifications", old, _items("a", "b"), first_run=not had)
        assert d1.is_empty and d1.first_run
        db.save_page_snapshot(conn, scan1, "notifications", _items("a", "b"), None)
        db.save_page_diff(conn, scan1, d1)
        db.finish_scan(conn, scan1, status="ok")

        # Run 2 — diffs against run 1, and must not see its own in-flight scan.
        scan2 = db.start_scan(conn, user_id)
        old2, had2 = db.load_latest_snapshot(conn, user_id, "notifications", before_scan_id=scan2)
        assert had2 and [i.uid for i in old2] == ["notification:a", "notification:b"]
        d2 = diff_page("notifications", old2, _items("a", "b", "c"), first_run=not had2)
        assert [i.title for i in d2.added] == ["c"]
        db.save_page_snapshot(conn, scan2, "notifications", _items("a", "b", "c"), None)
        db.save_page_diff(conn, scan2, d2)
        db.finish_scan(conn, scan2, status="ok", change_count=d2.count)

        # Both states are still readable — the whole point of the rewrite.
        history = db.page_history(conn, user_id, "notifications")
        assert [h["scan_id"] for h in history] == [scan2, scan1]
        assert [h["item_count"] for h in history] == [3, 2]

        earlier = db.snapshot_items(conn, user_id, history[1]["snapshot_id"])
        assert [i.title for i in earlier] == ["a", "b"]
        conn.close()


def test_changed_fields_survive_the_round_trip():
    with tempfile.TemporaryDirectory() as td:
        conn, user_id = _fresh(td)
        before = [Item.from_fields("survey", "Exit Survey", uid="survey:1", status="Open")]
        after = [Item.from_fields("survey", "Exit Survey", uid="survey:1", status="Closed")]

        scan = db.start_scan(conn, user_id)
        d = diff_page("surveys", before, after)
        assert d.changed[0].changed_fields["status"] == ("Open", "Closed")
        db.save_page_diff(conn, scan, d)

        import json

        row = db.diffs_for_scan(conn, scan)[0]
        changed = json.loads(row["changed_json"])
        # Tuples become JSON arrays; the before/after pair must still be intact.
        assert changed[0]["changed_fields"]["status"] == ["Open", "Closed"]
        conn.close()


def test_auth_state_is_encrypted_at_rest():
    with tempfile.TemporaryDirectory() as td:
        conn, user_id = _fresh(td)
        state = {"cookies": [{"name": "sessionid", "value": "super-secret-value"}], "origins": []}

        db.save_auth_state(conn, user_id, state)
        assert db.load_auth_state(conn, user_id) == state
        assert db.get_user(conn, user_id)["needs_reauth"] == 0

        blob = conn.execute("SELECT encrypted_state FROM auth_state").fetchone()[0]
        assert b"super-secret-value" not in blob, "session cookie stored in the clear"

        db.clear_auth_state(conn, user_id)
        assert db.load_auth_state(conn, user_id) is None
        assert db.get_user(conn, user_id)["needs_reauth"] == 1
        conn.close()


def test_retention_keeps_scans_that_found_something():
    with tempfile.TemporaryDirectory() as td:
        conn, user_id = _fresh(td)
        boring = db.start_scan(conn, user_id)
        interesting = db.start_scan(conn, user_id)
        db.finish_scan(conn, boring, status="ok", change_count=0)
        db.finish_scan(conn, interesting, status="ok", change_count=3)
        # Backdate both well past the retention window.
        conn.execute("UPDATE scans SET started_at = '2020-01-01T00:00:00+00:00'")
        conn.commit()

        prunable = [r["id"] for r in db.prunable_scans(conn, keep_days=30)]
        assert prunable == [boring], prunable

        db.delete_scans(conn, prunable)
        assert [s["id"] for s in db.list_scans(conn, user_id)] == [interesting]
        conn.close()


def _run_all():
    for fn in (
        test_snapshots_accumulate_and_first_run_seeds,
        test_changed_fields_survive_the_round_trip,
        test_auth_state_is_encrypted_at_rest,
        test_retention_keeps_scans_that_found_something,
    ):
        fn()
        print(f"  ok  {fn.__name__}")
    print("\n4 tests passed.")


if __name__ == "__main__":
    _run_all()
