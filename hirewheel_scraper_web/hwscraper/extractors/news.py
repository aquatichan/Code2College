"""Extractor for /news/ — the Newsfeed.

The sidebar lists every issue as <a class="news-sidebar-item"> linking to
/news/<id>. A new issue appearing there is the signal. The id in the href is a
rock-solid uid.
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from . import extractor, clean
from ..models import Item


@extractor("news")
def parse(soup: BeautifulSoup) -> list[Item]:
    items: list[Item] = []
    for a in soup.select("a.news-sidebar-item"):
        href = a.get("href")
        title = clean(_text(a, ".news-sidebar-item-title")) or "(untitled issue)"
        items.append(
            Item.from_fields(
                "news_issue",
                title,
                uid=f"news:{href}" if href else None,
                date=clean(_text(a, ".news-sidebar-item-date")),
                href=href,
            )
        )
    return items


def _text(node, sel: str) -> str:
    el = node.select_one(sel)
    return el.get_text() if el else ""
