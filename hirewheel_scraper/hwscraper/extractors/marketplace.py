"""Extractor for /marketplace/browse — self-serve employer projects.

This is the highest-signal page: a new <a class="pj-card"> means a fresh paid
opportunity a student can register interest in. The default view is the "Open
projects" tab, so any card here is a live opportunity.

We capture stable fields only (title, goal, platforms, XP). We deliberately skip
any live "interest window closing in…" countdown text so a ticking timer never
shows up as a false 'changed' diff.
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from . import extractor, clean
from ..models import Item


@extractor("marketplace")
def parse(soup: BeautifulSoup) -> list[Item]:
    items: list[Item] = []
    for card in soup.select("a.pj-card"):
        href = card.get("href")
        title_el = card.select_one(".pj-title, h3, h2")
        title = clean(title_el.get_text() if title_el else "") or "(untitled project)"
        pills = [clean(p.get_text()) for p in card.select(".pill")]
        items.append(
            Item.from_fields(
                "marketplace_project",
                title,
                uid=f"marketplace:{href}" if href else None,
                goal=clean(_text(card, ".goal")),
                platforms=clean(_text(card, ".platforms")),
                xp=clean(_text(card, ".xp")),
                pills=pills,
                href=href,
            )
        )
    return items


def _text(node, sel: str) -> str:
    el = node.select_one(sel)
    return el.get_text() if el else ""
