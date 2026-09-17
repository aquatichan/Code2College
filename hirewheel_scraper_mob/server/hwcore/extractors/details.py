"""Extractors for detail pages reached from a listing page.

These are registered under reserved `_child:` keys rather than a page key,
because their pages are discovered at scan time (a news issue that did not exist
last week) rather than listed in the config.

Scoping matters here. A news article page also renders a "Past issues" sidebar
listing every other issue, so hashing the whole page would make *every* article
look changed the moment a new one is published. These deliberately read only the
article's own body.
"""

from __future__ import annotations

import hashlib

from bs4 import BeautifulSoup

from . import extractor, clean
from ._common import main_of
from ..models import Item

_CHROME = ("nav", "header", "footer", ".navbar", ".breadcrumb")


def _content(soup: BeautifulSoup, *preferred: str):
    """The page's own content: a preferred container if present, else main."""
    for sel in preferred:
        node = soup.select_one(sel)
        if node is not None:
            return node
    main = main_of(soup)
    for sel in _CHROME:
        for n in main.select(sel):
            n.decompose()
    return main


def _signature(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


@extractor("_child:news_article")
def parse_news_article(soup: BeautifulSoup) -> list[Item]:
    body = _content(soup, ".news-reader-body")
    meta = soup.select_one(".news-reader-meta")

    items: list[Item] = []

    # Sections give a diff something specific to point at when an issue is edited.
    for section in body.select(".nl-section-banner, .nl-callout-body"):
        title = clean(section.get_text(" "))[:70]
        if not title:
            continue
        items.append(
            Item.from_fields(
                "news_section",
                title,
                uid=f"news_section:{_signature(title)}",
                body=clean(section.get_text(" "))[:400] or None,
            )
        )

    # Plus one item covering the whole article, so an edit anywhere is caught
    # even if it falls outside a recognised section.
    text = clean(body.get_text(" "))
    items.append(
        Item.from_fields(
            "news_article",
            clean(meta.get_text(" "))[:70] if meta else "Article",
            uid="news_article",
            published=clean(meta.get_text(" ")) if meta else None,
            length=len(text),
            signature=_signature(text),
        )
    )
    return items


@extractor("_child:event_detail")
def parse_event_detail(soup: BeautifulSoup) -> list[Item]:
    body = _content(soup)
    heading = body.find(["h1", "h2"])
    title = clean(heading.get_text(" ")) if heading else "Event"
    badges = [clean(b.get_text()) for b in body.select(".badge")]
    text = clean(body.get_text(" "))

    return [
        Item.from_fields(
            "event_detail",
            title,
            uid="event_detail",
            badges=badges or None,
            detail=text[:400] or None,
            signature=_signature(text),
        )
    ]
