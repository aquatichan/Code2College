"""Extractor for /college-pathways/ — partner colleges.

The page says "more coming soon", so the signal is a NEW partner appearing.
Each partner is an <a class="cp-partner-card"> in the .cp-partner-grid. We key
off the partner name (stable) since cards may not carry a real href.
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from . import extractor, clean
from ..models import Item


@extractor("college_pathways")
def parse(soup: BeautifulSoup) -> list[Item]:
    items: list[Item] = []
    for card in soup.select("a.cp-partner-card, .cp-partner-grid .cp-partner-card"):
        name = clean(_text(card, ".cp-partner-name")) or "(unnamed partner)"
        href = card.get("href") if card.name == "a" else None
        tags = [clean(t.get_text()) for t in card.select(".cp-partner-tag")]
        items.append(
            Item.from_fields(
                "college_partner",
                name,
                uid=f"college_partner:{href}" if href and href != "#" else None,
                tagline=clean(_text(card, ".cp-partner-tagline")),
                tags=tags,
                cta=clean(_text(card, ".cp-partner-cta")),
                href=href,
            )
        )
    return items


def _text(node, sel: str) -> str:
    el = node.select_one(sel)
    return el.get_text() if el else ""
