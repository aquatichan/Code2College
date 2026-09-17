"""Extractor for /intern/meetings — interviews an employer scheduled.

Empty at build time. Note the empty-state is itself a `.meeting-card` containing
"No interviews scheduled yet", so we detect empty by that text (not by an alert)
before treating `.meeting-card`s as real interviews. Selectors for populated
cards are best-effort; refine once a real interview shows up.
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from . import extractor
from ._common import card_item, main_of, page_signature_item


@extractor("meetings")
def parse(soup: BeautifulSoup):
    main = main_of(soup)
    if "no interviews scheduled" in main.get_text(" ").lower():
        return []
    cards = main.select(".meeting-card")
    if cards:
        return [card_item("interview", c) for c in cards]
    return [page_signature_item("My Meetings", "meetings", main)]
