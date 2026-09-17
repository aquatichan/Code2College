"""Minimal APNs client: ES256 JWT auth over HTTP/2.

Apple requires HTTP/2 and a provider token signed with the ES256 key you
download from the developer portal (``AuthKey_XXXXXXXXXX.p8``). That is the whole
protocol, so there is no reason to pull in a push SDK — `cryptography` (already a
dependency, for session encryption) signs the token and `httpx` speaks HTTP/2.

The .p8 key is a long-lived credential for your entire Apple developer account.
It belongs in a file the server reads at startup, never in the repository.
"""

from __future__ import annotations

import base64
import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

from . import config

# Apple accepts a provider token for one hour. Refresh well before that.
_TOKEN_TTL_SECONDS = 45 * 60

_HOSTS = {
    "sandbox": "https://api.sandbox.push.apple.com",
    "production": "https://api.push.apple.com",
}


class APNsNotConfigured(RuntimeError):
    """Raised when push is requested but the APNs credentials are incomplete."""


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


@dataclass
class SendResult:
    """Outcome for one device token."""

    push_token: str
    ok: bool
    status: int
    reason: str | None = None

    @property
    def token_is_dead(self) -> bool:
        """True when Apple says this token will never work again.

        410 Gone means the app was uninstalled; BadDeviceToken means the token
        belongs to a different environment or is malformed. Either way, stop
        sending to it rather than retrying forever.
        """
        return self.status == 410 or self.reason in ("BadDeviceToken", "Unregistered")


class APNsClient:
    """Thread-safe sender. One instance per process; the runner reuses it."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jwt: str | None = None
        self._jwt_made_at = 0.0
        self._client: httpx.Client | None = None

    # -- configuration --------------------------------------------------------
    @staticmethod
    def is_configured() -> bool:
        return bool(
            config.APNS_KEY_PATH
            and config.APNS_KEY_ID
            and config.APNS_TEAM_ID
            and config.APNS_BUNDLE_ID
            and Path(config.APNS_KEY_PATH).is_file()
        )

    @staticmethod
    def _require_config() -> None:
        if APNsClient.is_configured():
            return
        missing = [
            name
            for name, value in (
                ("HW_APNS_KEY_PATH", config.APNS_KEY_PATH),
                ("HW_APNS_KEY_ID", config.APNS_KEY_ID),
                ("HW_APNS_TEAM_ID", config.APNS_TEAM_ID),
                ("HW_APNS_BUNDLE_ID", config.APNS_BUNDLE_ID),
            )
            if not value
        ]
        if not missing and not Path(config.APNS_KEY_PATH).is_file():
            raise APNsNotConfigured(f"APNs key file not found: {config.APNS_KEY_PATH}")
        raise APNsNotConfigured("APNs is not configured; missing: " + ", ".join(missing))

    # -- auth token -----------------------------------------------------------
    def _provider_token(self) -> str:
        """A cached ES256 JWT identifying this server to Apple."""
        with self._lock:
            fresh = self._jwt and (time.time() - self._jwt_made_at) < _TOKEN_TTL_SECONDS
            if fresh:
                return self._jwt  # type: ignore[return-value]

            self._require_config()
            key = serialization.load_pem_private_key(
                Path(config.APNS_KEY_PATH).read_bytes(), password=None
            )
            if not isinstance(key, ec.EllipticCurvePrivateKey):
                raise APNsNotConfigured("APNs key is not an EC private key; expected a .p8")

            header = _b64url(
                json.dumps({"alg": "ES256", "kid": config.APNS_KEY_ID}, separators=(",", ":")).encode()
            )
            payload = _b64url(
                json.dumps(
                    {"iss": config.APNS_TEAM_ID, "iat": int(time.time())}, separators=(",", ":")
                ).encode()
            )
            signing_input = f"{header}.{payload}".encode("ascii")

            # Apple wants the raw r||s pair, but cryptography emits DER.
            der = key.sign(signing_input, ec.ECDSA(hashes.SHA256()))
            r, s = decode_dss_signature(der)
            signature = r.to_bytes(32, "big") + s.to_bytes(32, "big")

            self._jwt = f"{header}.{payload}.{_b64url(signature)}"
            self._jwt_made_at = time.time()
            return self._jwt

    # -- transport ------------------------------------------------------------
    def _http(self) -> httpx.Client:
        if self._client is None:
            # HTTP/2 is mandatory for APNs, and httpx only speaks it when the
            # optional `h2` package is present. Say so plainly rather than
            # letting a bare ImportError surface from deep in a scan cycle.
            try:
                self._client = httpx.Client(http2=True, timeout=15.0)
            except ImportError as exc:
                raise APNsNotConfigured(
                    "APNs needs HTTP/2 support: pip install 'httpx[http2]'"
                ) from exc
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    # -- sending --------------------------------------------------------------
    def send(
        self,
        push_token: str,
        *,
        title: str,
        body: str,
        data: dict | None = None,
        collapse_id: str | None = None,
    ) -> SendResult:
        """Deliver one alert. Never raises for a per-device failure."""
        token = self._provider_token()
        host = _HOSTS.get(config.APNS_ENVIRONMENT, _HOSTS["sandbox"])

        payload: dict = {
            "aps": {
                "alert": {"title": title, "body": body},
                "sound": "default",
                # Let iOS group these in Notification Center rather than stacking
                # one entry per scan.
                "thread-id": "hirewheel-updates",
            }
        }
        payload.update(data or {})

        headers = {
            "authorization": f"bearer {token}",
            "apns-topic": config.APNS_BUNDLE_ID,
            "apns-push-type": "alert",
            "apns-priority": "10",
        }
        if collapse_id:
            headers["apns-collapse-id"] = collapse_id[:64]

        try:
            resp = self._http().post(
                f"{host}/3/device/{push_token}", json=payload, headers=headers
            )
        except httpx.HTTPError as exc:
            # A transport failure must never take down the scan that triggered it.
            print(f"[apns] transport error: {exc}")
            return SendResult(push_token, ok=False, status=0, reason=str(exc))

        if resp.status_code == 200:
            return SendResult(push_token, ok=True, status=200)

        reason = None
        try:
            reason = resp.json().get("reason")
        except ValueError:
            pass
        print(f"[apns] {resp.status_code} {reason or resp.text[:120]}")
        return SendResult(push_token, ok=False, status=resp.status_code, reason=reason)


CLIENT = APNsClient()
