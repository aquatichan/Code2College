"""Extractor for /program/dashboard — the Program Hub.

The page is tabbed (Deliverables, Assignments, AI Training, Live Courses,
History) but the other tabs load their content client-side, so v1 watches the
default Deliverables tab. Deliverables are required program tasks, so here we DO
track status changes (a new deliverable, or one going overdue, matters).

Each deliverable row is an <a href="#deliverable-..."> — the anchor slug is a
stable uid.
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from . import extractor, clean
from ..models import Item


@extractor("program")
def parse(soup: BeautifulSoup) -> list[Item]:
    items: list[Item] = []
    for row in soup.select('a[href^="#deliverable-"]'):
        href = row.get("href", "")
        title_el = row.select_one(".fw-semibold")
        title = clean(title_el.get_text() if title_el else "") or "(deliverable)"

        badge = row.select_one(".badge")
        status = clean(badge.get_text()) if badge else None

        sub_el = row.select_one(".text-muted, .small")
        detail = clean(sub_el.get_text()) if sub_el else ""
        # The sub text repeats the title as a prefix; trim it for a clean line.
        if title and detail.startswith(title):
            detail = detail[len(title):].strip(" ·")

        items.append(
            Item.from_fields(
                "deliverable",
                title,
                uid=f"deliverable:{href.lstrip('#')}",
                status=status,
                detail=detail,
            )
        )
    return items
