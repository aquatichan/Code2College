"""Compare a fresh scrape against the last snapshot → what's new/changed/gone."""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import Item


@dataclass
class ItemChange:
    """One changed item, with before/after field values for the interesting keys."""

    item: Item
    changed_fields: dict[str, tuple] = field(default_factory=dict)  # key -> (old, new)


@dataclass
class PageDiff:
    """The result of diffing one page. `is_empty` when nothing moved."""

    page_key: str
    added: list[Item] = field(default_factory=list)
    removed: list[Item] = field(default_factory=list)
    changed: list[ItemChange] = field(default_factory=list)
    first_run: bool = False  # no prior snapshot existed; we seeded, not diffed

    @property
    def is_empty(self) -> bool:
        return not (self.added or self.removed or self.changed)

    @property
    def count(self) -> int:
        return len(self.added) + len(self.removed) + len(self.changed)


def diff_page(
    page_key: str,
    old_items: list[Item],
    new_items: list[Item],
    *,
    first_run: bool = False,
) -> PageDiff:
    """Diff by stable uid: added = new uids, removed = gone uids, changed = same
    uid but different content hash."""
    old_by_uid = {it.uid: it for it in old_items}
    new_by_uid = {it.uid: it for it in new_items}

    result = PageDiff(page_key=page_key, first_run=first_run)

    # On the very first run there's nothing to compare against — seed silently
    # so we don't dump every existing item as "new".
    if first_run:
        return result

    for uid, new_it in new_by_uid.items():
        old_it = old_by_uid.get(uid)
        if old_it is None:
            result.added.append(new_it)
        elif old_it.content_hash() != new_it.content_hash():
            result.changed.append(
                ItemChange(item=new_it, changed_fields=_field_deltas(old_it, new_it))
            )

    for uid, old_it in old_by_uid.items():
        if uid not in new_by_uid:
            result.removed.append(old_it)

    return result


def _field_deltas(old: Item, new: Item) -> dict[str, tuple]:
    """Which fields differ, old value vs new value (title included as a field)."""
    deltas: dict[str, tuple] = {}
    if old.title != new.title:
        deltas["title"] = (old.title, new.title)
    keys = set(old.fields) | set(new.fields)
    for k in keys:
        ov, nv = old.fields.get(k), new.fields.get(k)
        if ov != nv:
            deltas[k] = (ov, nv)
    return deltas
