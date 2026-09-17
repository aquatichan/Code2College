"""Discovering detail pages linked from a listing page.

Some content only exists one level down: a newsletter's actual text lives on
`/news/364`, not on the newsfeed index, which shows only its title and date.

This is deliberately *not* a crawler. Only listings with a bounded, useful set of
children are followed, and each is capped. Learning Modules is the reason for the
caution — it links to 188 module pages, which would turn an 11-second scan into
minutes and multiply screenshot storage for very little signal.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

# Never follow more than this many children from one listing, whatever the page
# says. A listing that suddenly grows shouldn't be able to blow up a scan.
MAX_CHILDREN_PER_PAGE = 12


@dataclass(frozen=True)
class ChildPage:
    """A detail page to scan as if it were its own watched page."""

    key: str        # stable across scans, e.g. "news:364"
    url: str
    label: str      # shown in the app
    extractor: str  # reserved key in the extractor registry


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _news_children(soup: BeautifulSoup, base_url: str) -> list[ChildPage]:
    out: list[ChildPage] = []
    seen: set[str] = set()
    for a in (soup.find("main") or soup).select('a[href^="/news/"]'):
        href = (a.get("href") or "").split("?")[0].rstrip("/")
        ident = href.rsplit("/", 1)[-1]
        # Only numeric issue ids; skip the index and any category links.
        if not ident.isdigit() or href in seen:
            continue
        seen.add(href)
        title = _clean(a.get_text(" "))[:60] or f"Issue {ident}"
        out.append(
            ChildPage(
                key=f"news:{ident}",
                url=f"{base_url}{href}",
                label=f"Newsfeed · {title}",
                extractor="_child:news_article",
            )
        )
    return out


def _event_children(soup: BeautifulSoup, base_url: str) -> list[ChildPage]:
    out: list[ChildPage] = []
    seen: set[str] = set()
    for a in (soup.find("main") or soup).select('a[href^="/events/"]'):
        href = (a.get("href") or "").split("?")[0].rstrip("/")
        slug = href.rsplit("/", 1)[-1]
        if not slug or href in seen:
            continue
        seen.add(href)
        title = _clean(a.get_text(" "))[:60] or slug
        out.append(
            ChildPage(
                key=f"event:{slug}",
                url=f"{base_url}{href}",
                label=f"Event · {title}",
                extractor="_child:event_detail",
            )
        )
    return out


# Only these listings are followed. Adding a page here is a deliberate decision
# about scan cost, not something that should happen by accident.
_DISCOVERERS = {
    "news": _news_children,
    "special_events": _event_children,
}


def discover(page_key: str, soup: BeautifulSoup, base_url: str) -> list[ChildPage]:
    """Detail pages worth scanning from this listing, capped."""
    finder = _DISCOVERERS.get(page_key)
    if finder is None:
        return []
    try:
        return finder(soup, base_url)[:MAX_CHILDREN_PER_PAGE]
    except Exception as exc:
        # A listing whose markup moved shouldn't fail the parent's scan.
        print(f"[children] discovery failed for {page_key}: {exc}")
        return []
