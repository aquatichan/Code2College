"""Validate the notifications extractor and the diff engine against a fixture.

Runs standalone (`python -m tests.test_notifications`) or under pytest.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow `python -m tests.test_notifications` from the project root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hwscraper.diff import diff_page  # noqa: E402
from hwscraper.extractors import get_extractor, parse_html  # noqa: E402
from hwscraper.models import Item  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "notifications.html"


def _items():
    html = FIXTURE.read_text(encoding="utf-8")
    return get_extractor("notifications")(parse_html(html))


def test_extracts_both_notifications():
    items = _items()
    assert len(items) == 2
    assert {i.uid for i in items} == {"notification:1325", "notification:1324"}


def test_fields_parsed():
    top = next(i for i in _items() if i.uid == "notification:1325")
    assert "Milestone Catch-up was approved" in top.title
    assert top.fields["body"] == "You can now edit and resubmit your work."
    assert top.fields["action_url"] == "/student/modules/264"
    assert top.fields["ts"] == "2026-04-22T05:21:39Z"


def test_diff_detects_new_and_changed():
    new = _items()
    # Pretend last run only had 1324, and 1325 didn't exist yet.
    old = [i for i in new if i.uid == "notification:1324"]
    d = diff_page("notifications", old, new)
    assert [i.uid for i in d.added] == ["notification:1325"]
    assert not d.changed and not d.removed

    # Now flip a field on 1324 → should register as a change, not add/remove.
    changed_old = [
        Item.from_fields("notification", "old title", uid="notification:1324", body="x")
    ]
    d2 = diff_page("notifications", changed_old, [i for i in new if i.uid == "notification:1324"])
    assert len(d2.changed) == 1 and not d2.added and not d2.removed


def test_first_run_seeds_silently():
    d = diff_page("notifications", [], _items(), first_run=True)
    assert d.is_empty and d.first_run


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\n{len(fns)} tests passed.")


if __name__ == "__main__":
    _run_all()
