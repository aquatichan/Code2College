"""Extractor for /surveys/my — surveys grouped under 'Available now' / 'Completed'.

The signal is a NEW survey under "Available now" (something the student can act
on). We tag each card with its section header so the UI can show it. Cards are
generic Bootstrap with no data-ids, so we key off the survey title.
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from . import extractor, clean
from ..models import Item


@extractor("surveys")
def parse(soup: BeautifulSoup) -> list[Item]:
    main = soup.find("main") or soup
    items: list[Item] = []
    current_section = None

    for el in main.find_all(True):
        classes = el.get("class") or []
        if el.name == "h5" and "text-uppercase" in classes:
            current_section = clean(el.get_text())
        elif el.name == "div" and "card" in classes:
            title_el = el.select_one(".fw-semibold")
            title = clean(title_el.get_text() if title_el else "") or "(untitled survey)"
            sub_el = el.select_one(".text-muted")
            link = el.find("a", href=True) or el.find_parent("a", href=True)
            items.append(
                Item.from_fields(
                    "survey",
                    title,
                    section=current_section,
                    status=clean(sub_el.get_text()) if sub_el else None,
                    href=link.get("href") if link else None,
                )
            )
    return items
