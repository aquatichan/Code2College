"""The shared 'item' shape that extractors produce and the diff engine compares."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field, asdict
from typing import Any


def _slug(text: str) -> str:
    """A stable, filename-safe id derived from text (fallback when no real id)."""
    text = re.sub(r"\s+", " ", text or "").strip().lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:80] or "item"


@dataclass
class Item:
    """One thing on a page: a notification, a project card, a survey row, etc.

    `uid` is the stable identity used to tell items apart across runs. Prefer a
    real server id (data-notif-id, data-project-id, an href). When none exists,
    build one from the title via `from_fields`.

    `fields` holds the meaningful, human-visible content. Its hash decides
    whether an item *changed* between runs, so put only signal in here — never
    volatile noise like "2 minutes ago" or CSRF tokens.
    """

    uid: str
    kind: str                       # e.g. "notification", "project", "survey"
    title: str
    fields: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_fields(
        cls,
        kind: str,
        title: str,
        *,
        uid: str | None = None,
        **fields: Any,
    ) -> "Item":
        """Build an item, auto-deriving a uid from the title when not given."""
        clean = {k: v for k, v in fields.items() if v not in (None, "", [])}
        return cls(uid=uid or f"{kind}:{_slug(title)}", kind=kind, title=title, fields=clean)

    def content_hash(self) -> str:
        """Hash of the fields that, if changed, mean the item was updated."""
        payload = repr(sorted(self.fields.items())) + "||" + self.title
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["hash"] = self.content_hash()
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Item":
        return cls(uid=d["uid"], kind=d["kind"], title=d["title"], fields=d.get("fields", {}))
