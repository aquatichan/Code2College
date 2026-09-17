"""Extractor for /learning/modules — modules and their activities.

Signal we care about: NEW modules and NEW activities (fresh learning content).
We deliberately drop ``data-status`` and the "x / y complete" progress text —
those reflect the student's *own* progress and would spam the feed every time
they finish an activity. One item per module + one per activity.
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from . import extractor, clean
from ..models import Item, _slug


@extractor("modules")
def parse(soup: BeautifulSoup) -> list[Item]:
    items: list[Item] = []
    for mod in soup.select("section.learning-module"):
        title = clean(_text(mod, ".learning-module__title")) or "(untitled module)"
        mod_slug = _slug(title)
        items.append(
            Item.from_fields(
                "learning_module",
                title,
                uid=f"learning_module:{mod_slug}",
                description=clean(_text(mod, ".learning-module__description")),
            )
        )
        for act in mod.select("li.learning-activity"):
            act_title = clean(_text(act, ".learning-activity__title")) or "(untitled activity)"
            items.append(
                Item.from_fields(
                    "learning_activity",
                    act_title,
                    uid=f"learning_activity:{mod_slug}:{_slug(act_title)}",
                    xp=clean(_text(act, ".learning-activity__xp")),
                    module=title,
                )
            )
    return items


def _text(node, sel: str) -> str:
    el = node.select_one(sel)
    return el.get_text() if el else ""
