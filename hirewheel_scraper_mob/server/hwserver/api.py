"""HTTP API for the iOS app."""

from __future__ import annotations

import json
import sqlite3
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import appstore, authflow, config, db, media, push
from .runner import RUNNER

_conn: sqlite3.Connection | None = None


def conn() -> sqlite3.Connection:
    assert _conn is not None, "database not initialised"
    return _conn


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _conn
    config.ensure_dirs()
    _conn = db.connect()
    RUNNER.start()
    yield
    RUNNER.stop()
    _conn.close()
    _conn = None


app = FastAPI(title="Hirewheel Watch", lifespan=lifespan)


# -- auth ---------------------------------------------------------------------
def current_device(authorization: str = Header(default="")) -> sqlite3.Row:
    """Resolve the bearer token issued at enrollment to a device row."""
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "missing bearer token")
    device = db.device_by_token(conn(), authorization[7:].strip())
    if device is None:
        raise HTTPException(401, "unknown device token")
    return device


# -- schemas ------------------------------------------------------------------
class EnrollBody(BaseModel):
    label: str = "student"
    invite_code: str = ""
    push_token: str | None = None
    platform: str | None = "ios"


class PushTokenBody(BaseModel):
    push_token: str


class MutesBody(BaseModel):
    muted_pages: list[str]


class IntervalBody(BaseModel):
    interval_seconds: int | None = None


class PurchaseBody(BaseModel):
    """The `jwsRepresentation` of a StoreKit 2 verified transaction."""

    jws: str


# -- enrollment ---------------------------------------------------------------
@app.post("/enroll")
def enroll(body: EnrollBody) -> dict[str, Any]:
    """Create a user + first device. Gated by HW_INVITE_CODE when one is set."""
    if config.INVITE_CODE and body.invite_code != config.INVITE_CODE:
        raise HTTPException(403, "invalid invite code")
    c = conn()
    user_id = db.create_user(c, body.label)
    device_id, token = db.register_device(
        c, user_id, push_token=body.push_token, platform=body.platform
    )
    return {"user_id": user_id, "device_id": device_id, "device_token": token}


@app.get("/me")
def me(device: sqlite3.Row = Depends(current_device)) -> dict[str, Any]:
    c = conn()
    user = db.get_user(c, device["user_id"])
    if user is None:
        raise HTTPException(404, "user not found")
    last = db.last_scan_time(c, user["id"])
    return {
        "user_id": user["id"],
        "label": user["label"],
        "email": user["email"],
        "free_min_interval_seconds": config.FREE_MIN_INTERVAL_SECONDS,
        # Exactly which intervals this account may use. Purchases are
        # independent, so this is a set, not a threshold.
        "unlocked_interval_seconds": db.unlocked_intervals(c, user["id"]),
        "products": [
            {"product_id": pid, "interval_seconds": secs}
            for pid, secs in sorted(config.PRODUCTS.items(), key=lambda kv: -kv[1])
        ],
        "needs_reauth": bool(user["needs_reauth"]),
        "interval_seconds": user["interval_seconds"] or config.SCRAPE_INTERVAL_SECONDS,
        "last_scan_at": last.isoformat() if last else None,
        "runner_status": RUNNER.status_for(user["id"]),
        "muted_pages": json.loads(device["muted_pages"] or "[]"),
        "login_mode": config.LOGIN_MODE,
        # The app uses this to decide whether to run its own background-refresh
        # fallback: when remote push is live, it doesn't need to poll.
        "remote_push": push.backend_available(),
    }


@app.delete("/me")
def delete_me(device: sqlite3.Row = Depends(current_device)) -> dict[str, str]:
    """Full erasure: session state, devices, scans, diffs and every screenshot."""
    c = conn()
    user_id = device["user_id"]
    media.delete_user_media(user_id)
    db.delete_user(c, user_id)
    return {"status": "deleted"}


# -- hosted login -------------------------------------------------------------
@app.post("/auth/session")
def start_login(device: sqlite3.Row = Depends(current_device)) -> dict[str, Any]:
    try:
        sid, url = authflow.MANAGER.start(conn(), device["user_id"])
    except authflow.LoginUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    return {"session_id": sid, "login_url": url, "mode": config.LOGIN_MODE}


@app.get("/auth/session/{session_id}")
def poll_login(session_id: str, device: sqlite3.Row = Depends(current_device)) -> dict[str, Any]:
    row = db.get_login_session(conn(), session_id)
    if row is None or row["user_id"] != device["user_id"]:
        raise HTTPException(404, "no such login session")
    return {
        "session_id": row["id"],
        "status": row["status"],
        "detail": row["detail"],
        "login_url": row["login_url"],
        "expires_at": row["expires_at"],
    }


# -- devices ------------------------------------------------------------------
@app.post("/devices/push")
def set_push_token(
    body: PushTokenBody, device: sqlite3.Row = Depends(current_device)
) -> dict[str, Any]:
    db.update_device(conn(), device["id"], push_token=body.push_token)
    return {"status": "ok", "remote_push": push.backend_available()}


@app.patch("/devices/me")
def set_mutes(body: MutesBody, device: sqlite3.Row = Depends(current_device)) -> dict[str, Any]:
    known = set(config.PAGE_LABELS)
    unknown = [k for k in body.muted_pages if k not in known]
    if unknown:
        raise HTTPException(400, f"unknown page keys: {unknown}")
    db.update_device(conn(), device["id"], muted_pages=body.muted_pages)
    return {"muted_pages": sorted(set(body.muted_pages))}


@app.patch("/me/interval")
def set_interval(body: IntervalBody, device: sqlite3.Row = Depends(current_device)) -> dict[str, Any]:
    c = conn()
    seconds = body.interval_seconds
    if seconds is None:
        db.set_interval(c, device["user_id"], None)
        return {"interval_seconds": config.SCRAPE_INTERVAL_SECONDS}

    if seconds < 900:
        raise HTTPException(400, "interval must be at least 900 seconds")

    # Enforced here, not just hidden in the app: a client can call this directly,
    # and StoreKit's on-device check proves nothing to us.
    if not db.interval_is_unlocked(c, device["user_id"], seconds):
        raise HTTPException(
            402,
            f"Scanning every {seconds // 3600}h has not been purchased on this account.",
        )

    db.set_interval(c, device["user_id"], seconds)
    return {"interval_seconds": seconds}


# -- pages / scans / history --------------------------------------------------
@app.get("/pages")
def pages(device: sqlite3.Row = Depends(current_device)) -> list[dict[str, Any]]:
    """Watched pages, configured ones first, then any detail pages discovered."""
    out: list[dict[str, Any]] = [
        {"key": p.key, "label": p.label, "url": p.url, "parent": None} for p in config.PAGES
    ]
    known = {p.key for p in config.PAGES}
    for row in db.watched_pages(conn(), device["user_id"]):
        if row["page_key"] in known:
            continue
        out.append(
            {
                "key": row["page_key"],
                "label": row["label"],
                "url": "",
                "parent": row["parent_key"],
            }
        )
    return out


@app.get("/scans")
def list_scans(
    limit: int = Query(default=50, ge=1, le=200),
    device: sqlite3.Row = Depends(current_device),
) -> list[dict[str, Any]]:
    rows = db.list_scans(conn(), device["user_id"], limit=limit)
    return [
        {
            "id": r["id"],
            "started_at": r["started_at"],
            "finished_at": r["finished_at"],
            "status": r["status"],
            "error": r["error"],
            "change_count": r["change_count"],
        }
        for r in rows
    ]


def _diff_payload(row: sqlite3.Row, labels: dict[str, str] | None = None) -> dict[str, Any]:
    key = row["page_key"]
    label = (labels or {}).get(key) or config.PAGE_LABELS.get(key, key)
    return {
        "page_key": key,
        "label": label,
        "added": json.loads(row["added_json"]),
        "removed": json.loads(row["removed_json"]),
        "changed": json.loads(row["changed_json"]),
        "count": row["count"],
        "first_run": bool(row["first_run"]),
    }


@app.get("/scans/{scan_id}")
def get_scan(scan_id: int, device: sqlite3.Row = Depends(current_device)) -> dict[str, Any]:
    c = conn()
    scan = db.get_scan(c, device["user_id"], scan_id)
    if scan is None:
        raise HTTPException(404, "no such scan")

    shots = {s["page_key"]: s["screenshot_path"] for s in db.snapshots_for_scan(c, scan_id)}
    labels = db.page_labels(c, device["user_id"])
    diffs = []
    for row in db.diffs_for_scan(c, scan_id):
        payload = _diff_payload(row, labels)
        payload["screenshot_path"] = shots.get(row["page_key"])
        diffs.append(payload)

    return {
        "id": scan["id"],
        "started_at": scan["started_at"],
        "finished_at": scan["finished_at"],
        "status": scan["status"],
        "error": scan["error"],
        "change_count": scan["change_count"],
        "pages": diffs,
    }


@app.get("/pages/{page_key}/history")
def page_history(
    page_key: str,
    limit: int = Query(default=100, ge=1, le=500),
    device: sqlite3.Row = Depends(current_device),
) -> list[dict[str, Any]]:
    """The timeline scrubber's data: every stored state of one page, newest first."""
    if page_key not in config.PAGE_LABELS and page_key not in db.page_labels(
        conn(), device["user_id"]
    ):
        raise HTTPException(404, "unknown page")
    rows = db.page_history(conn(), device["user_id"], page_key, limit=limit)
    return [
        {
            "snapshot_id": r["snapshot_id"],
            "scan_id": r["scan_id"],
            "captured_at": r["captured_at"],
            "item_count": r["item_count"],
            "change_count": r["change_count"],
            "screenshot_path": r["screenshot_path"],
        }
        for r in rows
    ]


@app.get("/snapshots/{snapshot_id}")
def get_snapshot(snapshot_id: int, device: sqlite3.Row = Depends(current_device)) -> dict[str, Any]:
    items = db.snapshot_items(conn(), device["user_id"], snapshot_id)
    if items is None:
        raise HTTPException(404, "no such snapshot")
    return {"snapshot_id": snapshot_id, "items": [i.to_dict() for i in items]}


@app.get("/media/{path:path}")
def get_media(path: str, device: sqlite3.Row = Depends(current_device)) -> FileResponse:
    # Stored paths start with the owning user's id, so this is both the
    # ownership check and the guard against reading someone else's screenshots.
    if not path.startswith(f"{device['user_id']}/"):
        raise HTTPException(403, "not your media")
    try:
        full = media.resolve(path)
    except ValueError:
        raise HTTPException(400, "bad path") from None
    if not full.is_file():
        raise HTTPException(404, "no such screenshot")
    return FileResponse(full, media_type="image/webp")


# -- purchases ----------------------------------------------------------------
@app.post("/purchases")
def record_purchase(
    body: PurchaseBody, device: sqlite3.Row = Depends(current_device)
) -> dict[str, Any]:
    """Record a StoreKit purchase after verifying Apple signed it.

    The app posts every entitlement it holds on launch and after a restore, so
    this is idempotent by design.
    """
    try:
        purchase = appstore.verify_transaction(body.jws)
    except appstore.InvalidTransaction as exc:
        raise HTTPException(400, str(exc)) from exc

    c = conn()
    db.record_purchase(
        c,
        device["user_id"],
        product_id=purchase.product_id,
        original_transaction_id=purchase.original_transaction_id,
        interval_seconds=purchase.interval_seconds,
        purchased_at=purchase.purchased_at.isoformat(),
        signature_verified=purchase.signature_verified,
        revoked=purchase.revoked,
        environment=purchase.environment,
    )
    return {
        "product_id": purchase.product_id,
        "revoked": purchase.revoked,
        "signature_verified": purchase.signature_verified,
        "environment": purchase.environment,
        "unlocked_interval_seconds": db.unlocked_intervals(c, device["user_id"]),
    }


@app.get("/purchases")
def list_purchases(device: sqlite3.Row = Depends(current_device)) -> dict[str, Any]:
    c = conn()
    rows = db.purchases_for_user(c, device["user_id"])
    return {
        "unlocked_interval_seconds": db.unlocked_intervals(c, device["user_id"]),
        "purchases": [
            {
                "product_id": r["product_id"],
                "interval_seconds": r["interval_seconds"],
                "purchased_at": r["purchased_at"],
                "revoked": bool(r["revoked"]),
                "signature_verified": bool(r["signature_verified"]),
                "environment": r["environment"],
            }
            for r in rows
        ],
    }


# -- manual scan --------------------------------------------------------------
@app.post("/scan-now")
def scan_now(device: sqlite3.Row = Depends(current_device)) -> dict[str, str]:
    RUNNER.trigger(device["user_id"])
    return {"status": "queued"}
