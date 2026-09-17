"""Extractor for /internship-prep/ — the Internship Prep Projects grid.

Each project is an <article class="elite102-card"> with a stable link slug we use
as the uid. We track new projects appearing and per-user status changes
(Not Started → In Progress → Completed).
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from . import extractor, clean
from ..models import Item


@extractor("internship_prep")
def parse(soup: BeautifulSoup) -> list[Item]:
    items: list[Item] = []
    for card in soup.select("article.elite102-card"):
        title = clean(_text(card, ".elite102-card__title")) or "(untitled project)"
        btn = card.select_one("a.elite102-card__btn")
        href = btn.get("href") if btn else None
        tags = [clean(t.get_text()) for t in card.select(".elite102-card__tag")]
        items.append(
            Item.from_fields(
                "prep_project",
                title,
                uid=f"prep_project:{href}" if href else None,
                category=clean(_text(card, ".elite102-card__category")),
                description=clean(_text(card, ".elite102-card__description")),
                status=clean(_text(card, ".elite102-card__status")),
                tags=tags,
                href=href,
            )
        )
    return items


def _text(node, sel: str) -> str:
    el = node.select_one(sel)
    return el.get_text() if el else ""
