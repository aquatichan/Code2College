"""Notification delivery.

One notification per cycle, never one per item: a scan that turns up six new
marketplace projects should buzz once and say "6 updates", not six times. That
restraint is the whole reason this is better than the desktop window.

Two backends, chosen by ``HW_PUSH_BACKEND``:

* ``none`` (default) — device tokens are still stored, but nothing is sent. The
  app falls back to background refresh plus a *local* notification it raises
  itself, which needs no Apple Developer account. Delivery is later and less
  reliable, because iOS decides when to wake the app.
* ``apns`` — real remote push. Instant, works with the app closed, and needs a
  paid account plus a .p8 auth key.

The interface is identical either way, so flipping the env var is the only change
required when the account arrives.
"""

from __future__ import annotations

import sqlite3

from . import config, db
from .apns import CLIENT, APNsNotConfigured
from .pipeline import CycleResult


def backend_available() -> bool:
    """Whether remote push can actually be delivered right now."""
    return config.PUSH_BACKEND == "apns" and CLIENT.is_configured()


def _targets(conn: sqlite3.Connection, user_id: str) -> list[tuple[str, list[str]]]:
    """(push_token, muted_page_keys) for every device that can receive push."""
    import json

    out: list[tuple[str, list[str]]] = []
    for dev in db.devices_for_user(conn, user_id):
        token = dev["push_token"]
        if not token:
            continue
        try:
            muted = json.loads(dev["muted_pages"] or "[]")
        except json.JSONDecodeError:
            muted = []
        out.append((token, muted))
    return out


def _deliver(
    conn: sqlite3.Connection,
    messages: list[tuple[str, str, str, dict, str | None]],
) -> int:
    """Send (token, title, body, data, collapse_id) tuples; retire dead tokens."""
    if not messages:
        return 0
    if config.PUSH_BACKEND == "none":
        # Expected and fine: the app polls in the background instead.
        print(f"[push] backend=none; {len(messages)} notification(s) not sent")
        return 0
    if not CLIENT.is_configured():
        print("[push] backend=apns but credentials are incomplete; nothing sent")
        return 0

    sent = 0
    for token, title, body, data, collapse_id in messages:
        try:
            result = CLIENT.send(token, title=title, body=body, data=data, collapse_id=collapse_id)
        except APNsNotConfigured as exc:
            print(f"[push] {exc}")
            return sent
        if result.ok:
            sent += 1
        elif result.token_is_dead:
            db.drop_push_token(conn, token)
    return sent


def notify_cycle(conn: sqlite3.Connection, user_id: str, result: CycleResult) -> int:
    """Tell every non-muted device what changed. Returns notifications sent."""
    changed = result.changed_pages
    if not changed:
        return 0

    messages = []
    for token, muted in _targets(conn, user_id):
        relevant = [d for d in changed if d.page_key not in muted]
        if not relevant:
            continue
        total = sum(d.count for d in relevant)
        labels = [config.PAGE_LABELS.get(d.page_key, d.page_key) for d in relevant]
        messages.append(
            (
                token,
                f"Hirewheel — {total} update{'' if total == 1 else 's'}",
                ", ".join(labels),
                {"type": "cycle", "scan_id": result.scan_id},
                f"scan-{result.scan_id}",
            )
        )
    return _deliver(conn, messages)


def notify_reauth(conn: sqlite3.Connection, user_id: str) -> int:
    """The session expired. On the desktop this was a banner telling you to go run
    a CLI command; here it is a tap straight into the login flow."""
    messages = [
        (
            token,
            "Hirewheel sign-in needed",
            "Your session expired. Tap to sign in again.",
            {"type": "reauth"},
            f"reauth-{user_id}",
        )
        for token, _muted in _targets(conn, user_id)
    ]
    return _deliver(conn, messages)
