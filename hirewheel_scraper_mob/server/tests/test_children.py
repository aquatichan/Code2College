"""Detail-page discovery.

Following links is where a watcher can accidentally become a crawler, so the
bounds matter as much as the behaviour: only listings that opt in are followed,
the count is capped, and keys stay stable so a page diffs against itself across
scans rather than looking brand new every time.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bs4 import BeautifulSoup  # noqa: E402

from hwcore.extractors import get_extractor  # noqa: E402
from hwserver import children  # noqa: E402

BASE = "https://www.hirewheel.ai"

NEWS_INDEX = """
<main>
  <a href="/news/364">Sep 4, 2026 Internships Newsletter</a>
  <a href="/news/331">Aug 21, 2026 Internships Newsletter</a>
  <a href="/news/">Newsfeed home</a>
  <a href="/news/category/updates">Updates</a>
</main>
"""

EVENTS_INDEX = """
<main>
  <a href="/events/orientation-fall-2026">Student Orientation</a>
  <a href="/events/orientation-fall-2026?ref=x">Student Orientation again</a>
</main>
"""


def test_news_children_are_numeric_issues_only():
    found = children.discover("news", BeautifulSoup(NEWS_INDEX, "html.parser"), BASE)
    keys = [c.key for c in found]
    assert keys == ["news:364", "news:331"], keys
    assert found[0].url == f"{BASE}/news/364"
    assert found[0].extractor == "_child:news_article"
    # The index itself and category pages are not articles.
    assert not any("category" in c.url for c in found)


def test_event_children_dedupe_query_strings():
    found = children.discover("special_events", BeautifulSoup(EVENTS_INDEX, "html.parser"), BASE)
    assert [c.key for c in found] == ["event:orientation-fall-2026"]


def test_keys_are_stable_across_scans():
    """A page must diff against itself, not appear new every cycle."""
    a = children.discover("news", BeautifulSoup(NEWS_INDEX, "html.parser"), BASE)
    b = children.discover("news", BeautifulSoup(NEWS_INDEX, "html.parser"), BASE)
    assert [c.key for c in a] == [c.key for c in b]


def test_only_opted_in_listings_are_followed():
    """Learning Modules links to 188 detail pages; following it would be ruinous."""
    html = BeautifulSoup('<main><a href="/learning/modules/102">Module</a></main>', "html.parser")
    assert children.discover("modules", html, BASE) == []
    assert children.discover("notifications", html, BASE) == []


def test_child_count_is_capped():
    links = "".join(f'<a href="/news/{i}">Issue {i}</a>' for i in range(100, 160))
    found = children.discover("news", BeautifulSoup(f"<main>{links}</main>", "html.parser"), BASE)
    assert len(found) == children.MAX_CHILDREN_PER_PAGE


def test_broken_markup_does_not_break_the_parent_scan():
    assert children.discover("news", BeautifulSoup("<main></main>", "html.parser"), BASE) == []


def test_news_article_ignores_the_past_issues_sidebar():
    """The sidebar lists every other issue; hashing it would make each article
    look changed whenever a new one is published."""
    html = """
    <main>
      <aside><a href="/news/331">Aug 21, 2026 Internships Newsletter</a></aside>
      <div class="news-reader-meta">Sep 4, 2026 Internships Newsletter</div>
      <div class="news-reader-body">
        <div class="nl-section-banner">Key Announcements</div>
        <p>Applications open Monday.</p>
      </div>
    </main>
    """
    items = get_extractor("_child:news_article")(BeautifulSoup(html, "html.parser"))
    blob = " ".join(i.title + str(i.fields) for i in items)
    assert "Aug 21" not in blob, "sidebar content leaked into the article snapshot"
    assert any(i.kind == "news_section" for i in items)
    assert any(i.kind == "news_article" for i in items)


def _run_all():
    for fn in (
        test_news_children_are_numeric_issues_only,
        test_event_children_dedupe_query_strings,
        test_keys_are_stable_across_scans,
        test_only_opted_in_listings_are_followed,
        test_child_count_is_capped,
        test_broken_markup_does_not_break_the_parent_scan,
        test_news_article_ignores_the_past_issues_sidebar,
    ):
        fn()
        print(f"  ok  {fn.__name__}")
    print("\n7 tests passed.")


if __name__ == "__main__":
    _run_all()
