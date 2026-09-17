"""Extractors for the Program Hub's non-default tabs, and the Marketplace examples tab.

Each of these is a separate server-rendered URL (`?tab=...`), so they are ordinary
pages as far as the pipeline is concerned — v1 simply never visited them.

Their bodies are Bootstrap `.card` blocks whose inner markup varies per tab
(enrollment status, live-class details, a history summary). Rather than guess a
bespoke selector for each, these reuse the card + whole-page-signature approach
already used for the pages that were empty at build time: real cards become
items, and if a tab's layout isn't recognised its text is hashed into a single
`page_change` item so a change is never silently missed.
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from . import extractor, clean
from ._common import card_item, main_of, page_signature_item
from ..models import Item

# The tab strip and breadcrumbs repeat on every Program Hub tab; hashing them
# would make every tab look identical and mask real changes.
_CHROME = ("nav", "header", "footer", ".navbar", ".breadcrumb", ".nav-tabs", ".nav-pills")


def _body(soup: BeautifulSoup):
    """The tab's own content, with the shared page chrome removed."""
    main = main_of(soup)
    for sel in _CHROME:
        for node in main.select(sel):
            node.decompose()
    return main


def _cards_or_signature(kind: str, label: str, page_key: str, soup: BeautifulSoup) -> list[Item]:
    body = _body(soup)
    cards = body.select(".card")
    if cards:
        items = [card_item(kind, c) for c in cards]
        # A card carrying no readable text is noise, not content.
        return [i for i in items if clean(i.title) and i.title != "(item)"]
    return [page_signature_item(label, page_key, body)]


@extractor("program_assignments")
def parse_assignments(soup: BeautifulSoup) -> list[Item]:
    return _cards_or_signature("assignment", "Assignments", "program_assignments", soup)


@extractor("program_ai_training")
def parse_ai_training(soup: BeautifulSoup) -> list[Item]:
    return _cards_or_signature("program_track", "AI Training", "program_ai_training", soup)


@extractor("program_fall")
def parse_fall(soup: BeautifulSoup) -> list[Item]:
    return _cards_or_signature("program_track", "Fall 2026", "program_fall", soup)


@extractor("program_courses")
def parse_courses(soup: BeautifulSoup) -> list[Item]:
    """Live classes: Zoom links, schedules, syllabus links — the highest-signal tab."""
    return _cards_or_signature("course", "Live Courses", "program_courses", soup)


@extractor("program_history")
def parse_history(soup: BeautifulSoup) -> list[Item]:
    """Loads client-side and may render an error state; the signature covers both."""
    return _cards_or_signature("history", "History", "program_history", soup)


@extractor("marketplace_examples")
def parse_marketplace_examples(soup: BeautifulSoup) -> list[Item]:
    """Same card markup as the open-projects tab, with a signature safety net."""
    body = _body(soup)
    cards = body.select("a.pj-card")
    if cards:
        return [card_item("marketplace_example", c) for c in cards]
    return _cards_or_signature(
        "marketplace_example", "Marketplace Examples", "marketplace_examples", soup
    )
