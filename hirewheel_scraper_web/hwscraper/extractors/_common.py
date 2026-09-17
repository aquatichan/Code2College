"""Shared helpers for extractors — used by pages that were empty at build time.

For /intern/my_projects and /intern/meetings we couldn't see the populated card
markup (no data assigned yet), so these helpers turn generic Bootstrap cards into
Items and provide a whole-page 'signature' safety net so a real change is never
missed even if the guessed selectors don't match.
"""

from __future__ import annotations

import hashlib

from bs4 import BeautifulSoup

from . import clean
from ..models import Item, _slug


def main_of(soup: BeautifulSoup):
    return soup.find("main") or soup


def looks_empty(main, *markers: str) -> bool:
    """True if an empty-state alert with one of the marker phrases is present."""
    if main.find(class_="alert") is None:
        return False
    text = main.get_text(" ").lower()
    return any(m.lower() in text for m in markers)


def card_item(kind: str, card) -> Item:
    """Best-effort conversion of a generic card/list-item into an Item."""
    head = card.find(["h1", "h2", "h3", "h4", "h5"]) or card.select_one(".fw-semibold, .title")
    title = clean(head.get_text()) if head else (clean(card.get_text())[:60] or "(item)")

    link = card.find("a", href=True)
    href = link.get("href").split("?")[0] if link else None

    badge = card.select_one(".badge")
    status = clean(badge.get_text()) if badge else None

    sub = None
    for sel in (".text-muted", ".small", "p"):
        el = card.select_one(sel)
        cand = clean(el.get_text()) if el else ""
        if cand and cand != title:
            sub = cand
            break

    uid = f"{kind}:{href}" if href else f"{kind}:{_slug(title)}"
    return Item.from_fields(kind, title, uid=uid, status=status, detail=sub, href=href)


def page_signature_item(label: str, page_key: str, main) -> Item:
    """A single item whose hash covers the whole page — the last-resort net."""
    sig = hashlib.sha1(clean(main.get_text(" ")).encode("utf-8")).hexdigest()[:12]
    return Item.from_fields("page_change", f"{label} — page changed", uid=f"page:{page_key}", signature=sig)


def cards_or_signature(kind: str, label: str, page_key: str, main, empty_markers, card_selectors):
    """Standard flow for the two currently-empty pages."""
    if looks_empty(main, *empty_markers):
        return []
    cards = main.select(card_selectors)
    if cards:
        return [card_item(kind, c) for c in cards]
    # Non-empty but unrecognized layout → don't lose the change.
    return [page_signature_item(label, page_key, main)]
