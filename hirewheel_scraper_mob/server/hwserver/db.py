"""Append-only storage: every scan is kept, nothing is ever overwritten.

This replaces the desktop project's `store.py`, which kept exactly one JSON file
per page and clobbered it each cycle. That design made change detection work but
made history impossible — there was never more than one past state to look at.

Here each cycle appends a `scans` row plus one `page_snapshots` row per page
(with its own screenshot) and one `page_diffs` row per page. Diffing still works
the same way: `load_latest_snapshot` hands the previous run's items to the
unchanged `hwcore.diff.diff_page`.
"""

from __future__ import annotations

import json
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from hwcore.diff import ItemChange, PageDiff
from hwcore.models import Item

from . import config, crypto

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    label         TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    needs_reauth  INTEGER NOT NULL DEFAULT 1,
    interval_seconds INTEGER,
    email         TEXT
);

CREATE TABLE IF NOT EXISTS auth_state (
    user_id         TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    encrypted_state BLOB NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS devices (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token       TEXT NOT NULL UNIQUE,
    push_token  TEXT,
    platform    TEXT,
    muted_pages TEXT NOT NULL DEFAULT '[]',
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scans (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    started_at   TEXT NOT NULL,
    finished_at  TEXT,
    status       TEXT NOT NULL,
    error        TEXT,
    change_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS page_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id         INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    page_key        TEXT NOT NULL,
    items_json      TEXT NOT NULL,
    item_count      INTEGER NOT NULL,
    screenshot_path TEXT,
    captured_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS page_diffs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id      INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    page_key     TEXT NOT NULL,
    added_json   TEXT NOT NULL,
    removed_json TEXT NOT NULL,
    changed_json TEXT NOT NULL,
    count        INTEGER NOT NULL,
    first_run    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS watched_pages (
    user_id      TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    page_key     TEXT NOT NULL,
    label        TEXT NOT NULL,
    parent_key   TEXT,
    last_seen_at TEXT NOT NULL,
    PRIMARY KEY (user_id, page_key)
);

CREATE TABLE IF NOT EXISTS purchases (
    user_id                 TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product_id              TEXT NOT NULL,
    original_transaction_id TEXT NOT NULL,
    interval_seconds        INTEGER NOT NULL,
    purchased_at            TEXT NOT NULL,
    recorded_at             TEXT NOT NULL,
    signature_verified      INTEGER NOT NULL DEFAULT 0,
    revoked                 INTEGER NOT NULL DEFAULT 0,
    environment             TEXT NOT NULL DEFAULT 'Unknown',
    PRIMARY KEY (user_id, original_transaction_id)
);

CREATE TABLE IF NOT EXISTS login_sessions (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status     TEXT NOT NULL,
    detail     TEXT,
    login_url  TEXT,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_scans_user      ON scans(user_id, id DESC);
CREATE INDEX IF NOT EXISTS idx_snapshots_scan  ON page_snapshots(scan_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_page  ON page_snapshots(page_key, scan_id DESC);
CREATE INDEX IF NOT EXISTS idx_diffs_scan      ON page_diffs(scan_id);
CREATE INDEX IF NOT EXISTS idx_devices_user    ON devices(user_id);
CREATE INDEX IF NOT EXISTS idx_purchases_user  ON purchases(user_id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# -- connection ---------------------------------------------------------------
def connect(path: Path | str | None = None) -> sqlite3.Connection:
    """Open the database, creating it and its schema if needed.

    `path` is resolved at call time (not import time) so tests can point
    `config.DB_PATH` at a temp dir.
    """
    target = Path(path) if path is not None else config.DB_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    _migrate(conn)
    conn.commit()
    return conn


# Columns added after the first release. SQLite has no "ADD COLUMN IF NOT EXISTS",
# so compare against the live table rather than catching duplicate-column errors.
_ADDED_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("users", "email", "TEXT"),
    ("purchases", "environment", "TEXT NOT NULL DEFAULT 'Unknown'"),
)


def _migrate(conn: sqlite3.Connection) -> None:
    for table, column, decl in _ADDED_COLUMNS:
        existing = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


# -- serialization ------------------------------------------------------------
def _dump_items(items: Iterable[Item]) -> str:
    return json.dumps([it.to_dict() for it in items], ensure_ascii=False)


def _load_items(raw: str) -> list[Item]:
    return [Item.from_dict(d) for d in json.loads(raw)]


def _dump_changes(changes: Iterable[ItemChange]) -> str:
    return json.dumps(
        [
            {
                "item": c.item.to_dict(),
                "changed_fields": {k: list(v) for k, v in c.changed_fields.items()},
            }
            for c in changes
        ],
        ensure_ascii=False,
    )


# -- users --------------------------------------------------------------------
def create_user(conn: sqlite3.Connection, label: str) -> str:
    user_id = uuid.uuid4().hex
    conn.execute(
        "INSERT INTO users (id, label, created_at, needs_reauth) VALUES (?, ?, ?, 1)",
        (user_id, label, _now()),
    )
    conn.commit()
    return user_id


def get_user(conn: sqlite3.Connection, user_id: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def all_users(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM users ORDER BY created_at").fetchall()


def set_needs_reauth(conn: sqlite3.Connection, user_id: str, needs: bool) -> None:
    conn.execute("UPDATE users SET needs_reauth = ? WHERE id = ?", (1 if needs else 0, user_id))
    conn.commit()


def set_interval(conn: sqlite3.Connection, user_id: str, seconds: int | None) -> None:
    conn.execute("UPDATE users SET interval_seconds = ? WHERE id = ?", (seconds, user_id))
    conn.commit()


def set_email(conn: sqlite3.Connection, user_id: str, email: str | None) -> None:
    conn.execute("UPDATE users SET email = ? WHERE id = ?", (email, user_id))
    conn.commit()


# -- watched pages ------------------------------------------------------------
def record_watched_page(
    conn: sqlite3.Connection,
    user_id: str,
    page_key: str,
    label: str,
    parent_key: str | None = None,
) -> None:
    """Remember a page's human label.

    Pages discovered at scan time (a news issue that did not exist last week)
    have no entry in the static config, so their labels have to live somewhere.
    """
    conn.execute(
        "INSERT INTO watched_pages (user_id, page_key, label, parent_key, last_seen_at) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(user_id, page_key) DO UPDATE SET "
        "  label = excluded.label, parent_key = excluded.parent_key, "
        "  last_seen_at = excluded.last_seen_at",
        (user_id, page_key, label, parent_key, _now()),
    )
    conn.commit()


def watched_pages(conn: sqlite3.Connection, user_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM watched_pages WHERE user_id = ? ORDER BY parent_key IS NOT NULL, page_key",
        (user_id,),
    ).fetchall()


def page_labels(conn: sqlite3.Connection, user_id: str) -> dict[str, str]:
    return {r["page_key"]: r["label"] for r in watched_pages(conn, user_id)}


# -- purchases ----------------------------------------------------------------
def record_purchase(
    conn: sqlite3.Connection,
    user_id: str,
    *,
    product_id: str,
    original_transaction_id: str,
    interval_seconds: int,
    purchased_at: str,
    signature_verified: bool,
    revoked: bool,
    environment: str = "Unknown",
) -> None:
    """Store an entitlement. Keyed on Apple's original transaction id, so the app
    re-sending the same purchase (every launch, or after a restore) is harmless."""
    conn.execute(
        "INSERT INTO purchases (user_id, product_id, original_transaction_id, "
        "interval_seconds, purchased_at, recorded_at, signature_verified, revoked, "
        "environment) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(user_id, original_transaction_id) DO UPDATE SET "
        "  revoked = excluded.revoked, "
        "  signature_verified = excluded.signature_verified, "
        "  environment = excluded.environment, "
        "  recorded_at = excluded.recorded_at",
        (
            user_id,
            product_id,
            original_transaction_id,
            interval_seconds,
            purchased_at,
            _now(),
            1 if signature_verified else 0,
            1 if revoked else 0,
            environment,
        ),
    )
    conn.commit()


def purchases_for_user(conn: sqlite3.Connection, user_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM purchases WHERE user_id = ? ORDER BY interval_seconds", (user_id,)
    ).fetchall()


def unlocked_intervals(conn: sqlite3.Connection, user_id: str) -> list[int]:
    """Every interval this user has bought, plus the free one.

    Purchases are independent: buying the 6-hour interval unlocks the 6-hour
    interval and nothing else. A refunded purchase simply stops appearing.
    """
    rows = conn.execute(
        "SELECT DISTINCT interval_seconds FROM purchases WHERE user_id = ? AND revoked = 0",
        (user_id,),
    ).fetchall()
    unlocked = {r["interval_seconds"] for r in rows}
    unlocked.add(config.FREE_MIN_INTERVAL_SECONDS)
    return sorted(unlocked)


def interval_is_unlocked(conn: sqlite3.Connection, user_id: str, seconds: int) -> bool:
    """Anything at or slower than the free floor is always allowed."""
    if seconds >= config.FREE_MIN_INTERVAL_SECONDS:
        return True
    return seconds in set(unlocked_intervals(conn, user_id))


def delete_user(conn: sqlite3.Connection, user_id: str) -> None:
    """Full erasure — auth state, devices, scans, snapshots and diffs all cascade."""
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()


# -- auth state ---------------------------------------------------------------
def save_auth_state(conn: sqlite3.Connection, user_id: str, storage_state: dict[str, Any]) -> None:
    blob = crypto.encrypt(json.dumps(storage_state))
    conn.execute(
        "INSERT INTO auth_state (user_id, encrypted_state, updated_at) VALUES (?, ?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET encrypted_state = excluded.encrypted_state, "
        "updated_at = excluded.updated_at",
        (user_id, blob, _now()),
    )
    conn.execute("UPDATE users SET needs_reauth = 0 WHERE id = ?", (user_id,))
    conn.commit()


def load_auth_state(conn: sqlite3.Connection, user_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT encrypted_state FROM auth_state WHERE user_id = ?", (user_id,)
    ).fetchone()
    if row is None:
        return None
    raw = crypto.decrypt(row["encrypted_state"])
    if raw is None:  # key rotated or data corrupt — treat as signed out
        return None
    return json.loads(raw)


def clear_auth_state(conn: sqlite3.Connection, user_id: str) -> None:
    conn.execute("DELETE FROM auth_state WHERE user_id = ?", (user_id,))
    conn.execute("UPDATE users SET needs_reauth = 1 WHERE id = ?", (user_id,))
    conn.commit()


# -- devices ------------------------------------------------------------------
def register_device(
    conn: sqlite3.Connection,
    user_id: str,
    *,
    push_token: str | None = None,
    platform: str | None = None,
) -> tuple[str, str]:
    """Create a device row. Returns (device_id, bearer_token)."""
    device_id = uuid.uuid4().hex
    token = secrets.token_urlsafe(32)
    conn.execute(
        "INSERT INTO devices (id, user_id, token, push_token, platform, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (device_id, user_id, token, push_token, platform, _now()),
    )
    conn.commit()
    return device_id, token


def device_by_token(conn: sqlite3.Connection, token: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM devices WHERE token = ?", (token,)).fetchone()


def devices_for_user(conn: sqlite3.Connection, user_id: str) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM devices WHERE user_id = ?", (user_id,)).fetchall()


def update_device(
    conn: sqlite3.Connection,
    device_id: str,
    *,
    push_token: str | None = None,
    muted_pages: list[str] | None = None,
) -> None:
    if push_token is not None:
        conn.execute("UPDATE devices SET push_token = ? WHERE id = ?", (push_token, device_id))
    if muted_pages is not None:
        conn.execute(
            "UPDATE devices SET muted_pages = ? WHERE id = ?",
            (json.dumps(sorted(set(muted_pages))), device_id),
        )
    conn.commit()


def drop_push_token(conn: sqlite3.Connection, push_token: str) -> None:
    """APNs told us this token is dead (app uninstalled) — stop using it."""
    conn.execute("UPDATE devices SET push_token = NULL WHERE push_token = ?", (push_token,))
    conn.commit()


# -- scans --------------------------------------------------------------------
def start_scan(conn: sqlite3.Connection, user_id: str) -> int:
    cur = conn.execute(
        "INSERT INTO scans (user_id, started_at, status) VALUES (?, ?, 'running')",
        (user_id, _now()),
    )
    conn.commit()
    return int(cur.lastrowid)


def finish_scan(
    conn: sqlite3.Connection,
    scan_id: int,
    *,
    status: str,
    change_count: int = 0,
    error: str | None = None,
) -> None:
    conn.execute(
        "UPDATE scans SET finished_at = ?, status = ?, change_count = ?, error = ? WHERE id = ?",
        (_now(), status, change_count, error, scan_id),
    )
    conn.commit()


def last_scan_time(conn: sqlite3.Connection, user_id: str) -> datetime | None:
    row = conn.execute(
        "SELECT started_at FROM scans WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user_id,)
    ).fetchone()
    return datetime.fromisoformat(row["started_at"]) if row else None


def list_scans(conn: sqlite3.Connection, user_id: str, limit: int = 50) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM scans WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit)
    ).fetchall()


def get_scan(conn: sqlite3.Connection, user_id: str, scan_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM scans WHERE id = ? AND user_id = ?", (scan_id, user_id)
    ).fetchone()


# -- snapshots & diffs --------------------------------------------------------
def save_page_snapshot(
    conn: sqlite3.Connection,
    scan_id: int,
    page_key: str,
    items: list[Item],
    screenshot_path: str | None,
) -> None:
    conn.execute(
        "INSERT INTO page_snapshots "
        "(scan_id, page_key, items_json, item_count, screenshot_path, captured_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (scan_id, page_key, _dump_items(items), len(items), screenshot_path, _now()),
    )
    conn.commit()


def save_page_diff(conn: sqlite3.Connection, scan_id: int, diff: PageDiff) -> None:
    conn.execute(
        "INSERT INTO page_diffs "
        "(scan_id, page_key, added_json, removed_json, changed_json, count, first_run) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            scan_id,
            diff.page_key,
            _dump_items(diff.added),
            _dump_items(diff.removed),
            _dump_changes(diff.changed),
            diff.count,
            1 if diff.first_run else 0,
        ),
    )
    conn.commit()


def load_latest_snapshot(
    conn: sqlite3.Connection,
    user_id: str,
    page_key: str,
    *,
    before_scan_id: int | None = None,
) -> tuple[list[Item], bool]:
    """The most recent stored items for a page, and whether one existed at all.

    `before_scan_id` excludes the in-flight scan — the current cycle has already
    inserted its `scans` row by the time pages are being fetched, so without this
    a page could diff against itself.

    Returns (items, had_snapshot). `had_snapshot` False means first run: the
    caller seeds silently instead of reporting every existing item as new.
    """
    sql = (
        "SELECT s.items_json FROM page_snapshots s "
        "JOIN scans sc ON sc.id = s.scan_id "
        "WHERE sc.user_id = ? AND s.page_key = ?"
    )
    params: list[Any] = [user_id, page_key]
    if before_scan_id is not None:
        sql += " AND s.scan_id < ?"
        params.append(before_scan_id)
    sql += " ORDER BY s.scan_id DESC LIMIT 1"

    row = conn.execute(sql, params).fetchone()
    if row is None:
        return [], False
    return _load_items(row["items_json"]), True


def diffs_for_scan(conn: sqlite3.Connection, scan_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM page_diffs WHERE scan_id = ? ORDER BY page_key", (scan_id,)
    ).fetchall()


def snapshots_for_scan(conn: sqlite3.Connection, scan_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM page_snapshots WHERE scan_id = ? ORDER BY page_key", (scan_id,)
    ).fetchall()


def page_history(
    conn: sqlite3.Connection, user_id: str, page_key: str, limit: int = 100
) -> list[sqlite3.Row]:
    """Every stored state of one page, newest first — the timeline scrubber's data."""
    return conn.execute(
        "SELECT s.id AS snapshot_id, s.scan_id, s.page_key, s.item_count, "
        "       s.screenshot_path, s.captured_at, "
        "       sc.started_at, COALESCE(d.count, 0) AS change_count "
        "FROM page_snapshots s "
        "JOIN scans sc ON sc.id = s.scan_id "
        "LEFT JOIN page_diffs d ON d.scan_id = s.scan_id AND d.page_key = s.page_key "
        "WHERE sc.user_id = ? AND s.page_key = ? "
        "ORDER BY s.scan_id DESC LIMIT ?",
        (user_id, page_key, limit),
    ).fetchall()


def snapshot_items(conn: sqlite3.Connection, user_id: str, snapshot_id: int) -> list[Item] | None:
    row = conn.execute(
        "SELECT s.items_json FROM page_snapshots s JOIN scans sc ON sc.id = s.scan_id "
        "WHERE s.id = ? AND sc.user_id = ?",
        (snapshot_id, user_id),
    ).fetchone()
    return _load_items(row["items_json"]) if row else None


# -- retention ----------------------------------------------------------------
def prunable_scans(
    conn: sqlite3.Connection, keep_days: int = config.RETENTION_DAYS
) -> list[sqlite3.Row]:
    """Old scans that recorded no changes.

    Scans WITH changes are kept regardless of age — those are the history worth
    having. Boring empty scans are the ones that pile up.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=keep_days)).isoformat()
    return conn.execute(
        "SELECT id, user_id FROM scans WHERE started_at < ? AND change_count = 0", (cutoff,)
    ).fetchall()


def delete_scans(conn: sqlite3.Connection, scan_ids: list[int]) -> None:
    if not scan_ids:
        return
    marks = ",".join("?" * len(scan_ids))
    conn.execute(f"DELETE FROM scans WHERE id IN ({marks})", scan_ids)
    conn.commit()


# -- login sessions -----------------------------------------------------------
def create_login_session(conn: sqlite3.Connection, user_id: str, login_url: str, ttl_s: int) -> str:
    sid = uuid.uuid4().hex
    now = datetime.now(timezone.utc)
    conn.execute(
        "INSERT INTO login_sessions (id, user_id, status, login_url, created_at, expires_at) "
        "VALUES (?, ?, 'pending', ?, ?, ?)",
        (sid, user_id, login_url, now.isoformat(), (now + timedelta(seconds=ttl_s)).isoformat()),
    )
    conn.commit()
    return sid


def set_login_status(
    conn: sqlite3.Connection, sid: str, status: str, detail: str | None = None
) -> None:
    conn.execute(
        "UPDATE login_sessions SET status = ?, detail = ? WHERE id = ?", (status, detail, sid)
    )
    conn.commit()


def set_login_url(conn: sqlite3.Connection, sid: str, url: str) -> None:
    conn.execute("UPDATE login_sessions SET login_url = ? WHERE id = ?", (url, sid))
    conn.commit()


def get_login_session(conn: sqlite3.Connection, sid: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM login_sessions WHERE id = ?", (sid,)).fetchone()
