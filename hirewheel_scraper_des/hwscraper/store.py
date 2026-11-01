"""Persist per-page snapshots so we can diff this run against the last one."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from . import config
from .models import Item


def _path_for(page_key: str):
    return config.SNAPSHOT_DIR / f"{page_key}.json"


def load_snapshot(page_key: str) -> list[Item]:
    """Return the previously stored items for a page (empty on first ever run)."""
    path = _path_for(page_key)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        # A corrupt snapshot shouldn't crash a cycle — treat as "nothing seen yet".
        return []
    return [Item.from_dict(d) for d in data.get("items", [])]


def save_snapshot(page_key: str, items: list[Item]) -> None:
    """Overwrite the stored snapshot for a page with the current items."""
    config.ensure_dirs()
    payload: dict[str, Any] = {
        "page": page_key,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "items": [it.to_dict() for it in items],
    }
    _path_for(page_key).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def has_snapshot(page_key: str) -> bool:
    """True once we've stored at least one snapshot for this page."""
    return _path_for(page_key).exists()
