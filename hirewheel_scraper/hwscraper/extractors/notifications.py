"""Extractor for /intern/notifications.

Markup (server-rendered Bootstrap):
    <a class="... notif-item" data-notif-id="1325" data-item-type="notification"
       data-action-url="/student/modules/264">
      <div>…icon…</div>
      <div class="flex-grow-1 ...">
        <div>...<p class="mb-1 ...">TITLE</p>...
             <small class="notif-time" data-ts="2026-04-22T05:21:39Z">…</small></div>
        <div>BODY</div>
      </div>
    </a>

data-notif-id gives us a rock-solid stable id.
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from . import extractor, clean
from ..models import Item


@extractor("notifications")
def parse(soup: BeautifulSoup) -> list[Item]:
    items: list[Item] = []
    for node in soup.select("a.notif-item, [data-item-type='notification']"):
        notif_id = node.get("data-notif-id")
        title_el = node.select_one("p.mb-1") or node.find("p")
        title = clean(title_el.get_text() if title_el else "")

        time_el = node.select_one(".notif-time")
        ts = (time_el.get("data-ts") if time_el else None) or (
            clean(time_el.get_text()) if time_el else None
        )

        # Body = everything in the item text minus the title and the timestamp label.
        full = clean(node.get_text(" "))
        body = full
        if title:
            body = body.replace(title, "", 1)
        if time_el:
            body = body.replace(clean(time_el.get_text()), "", 1)
        body = clean(body)

        action_url = node.get("data-action-url")

        items.append(
            Item.from_fields(
                "notification",
                title or "(untitled notification)",
                uid=f"notification:{notif_id}" if notif_id else None,
                body=body or None,
                action_url=action_url,
                ts=ts,
            )
        )
    return items
