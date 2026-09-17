"""Per-page extractors: turn a page's HTML into a list of structured Items.

Each extractor is registered against a page key (see config.PAGES) via the
``@extractor`` decorator. Add a new page by dropping a module in this package
that imports ``extractor`` and decorates a ``parse(soup) -> list[Item]`` fn.
"""

from __future__ import annotations

import re
from typing import Callable

from bs4 import BeautifulSoup

from ..models import Item

# page_key -> function(soup) -> list[Item]
Extractor = Callable[[BeautifulSoup], list[Item]]
_REGISTRY: dict[str, Extractor] = {}


def extractor(page_key: str):
    """Register a function as the extractor for a page key."""

    def deco(fn: Extractor) -> Extractor:
        _REGISTRY[page_key] = fn
        return fn

    return deco


def get_extractor(page_key: str) -> Extractor | None:
    return _REGISTRY.get(page_key)


def parse_html(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def clean(text: str | None) -> str:
    """Collapse whitespace; the single most common cleanup extractors need."""
    return re.sub(r"\s+", " ", text or "").strip()


# Import extractor modules so their @extractor decorators run on package import.
# Keep this at the bottom to avoid circular imports.
from . import (  # noqa: E402,F401
    notifications,
    internship_prep,
    marketplace,
    college_pathways,
    learning_modules,
    surveys,
    news,
    program,
    special_events,
    my_projects,
    meetings,
)
