"""Extractor for /special-events — Current and Past events.

Both tab panels (#current-events, #past-events) live in the DOM. A new event in
the CURRENT panel is the signal (something to attend). Events have no stable id,
so we key off the title, and tag each with which panel it came from.
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from . import extractor, clean
from ..models import Item, _slug

_PANELS = (("current-events", "current"), ("past-events", "past"))


@extractor("special_events")
def parse(soup: BeautifulSoup) -> list[Item]:
    items: list[Item] = []
    for panel_id, status in _PANELS:
        panel = soup.select_one(f"#{panel_id}")
        if panel is None:
            continue
        for h in panel.select("h3.fw-bold"):
            title = clean(h.get_text()) or "(untitled event)"
            section = h.find_parent("section") or h.parent
            desc_el = section.select_one("p.text-muted") if section else None
            btn = section.find("a", href=True) if section else None
            badges = [clean(b.get_text()) for b in section.select(".badge")] if section else []
            items.append(
                Item.from_fields(
                    "event",
                    title,
                    uid=f"event:{status}:{_slug(title)}",
                    status=status,
                    when=clean(desc_el.get_text()) if desc_el else None,
                    badges=badges,
                    href=(btn.get("href") or "").split("?")[0] if btn else None,
                )
            )
    return items
