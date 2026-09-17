"""Extractor for /intern/my_projects — the student's assigned projects.

This page was empty at build time ("You currently have no assigned projects"),
so the card selectors are best-effort. When a project is assigned it will show
up as an added item; if the guessed selectors miss, the page-signature net still
flags that the page changed. Refine the selectors once real data appears.
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from . import extractor
from ._common import cards_or_signature, main_of


@extractor("my_projects")
def parse(soup: BeautifulSoup):
    return cards_or_signature(
        kind="assigned_project",
        label="My Assigned Projects",
        page_key="my_projects",
        main=main_of(soup),
        empty_markers=("no assigned projects",),
        card_selectors=".card, article, .list-group-item, .pj-card",
    )
