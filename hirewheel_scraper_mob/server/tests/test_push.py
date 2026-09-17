"""Push tests.

The APNs wire format cannot be tested against Apple without a paid account, but
the parts that are easy to get silently wrong — the ES256 provider token, and the
decision about which device tokens to retire — are checked here against a
self-generated key.
"""

from __future__ import annotations

import base64
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cryptography.hazmat.primitives import hashes, serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import ec  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature  # noqa: E402

from hwserver import apns, config  # noqa: E402
from hwserver.apns import APNsClient, SendResult  # noqa: E402


def _b64url_decode(segment: str) -> bytes:
    return base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))


def _write_p8(path: Path) -> ec.EllipticCurvePrivateKey:
    """A throwaway P-256 key in the same PEM shape Apple hands out."""
    key = ec.generate_private_key(ec.SECP256R1())
    path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    return key


def test_provider_token_is_a_verifiable_es256_jwt():
    with tempfile.TemporaryDirectory() as td:
        key_path = Path(td) / "AuthKey_ABC1234567.p8"
        key = _write_p8(key_path)

        config.APNS_KEY_PATH = str(key_path)
        config.APNS_KEY_ID = "ABC1234567"
        config.APNS_TEAM_ID = "TEAM123456"
        config.APNS_BUNDLE_ID = "com.example.app"

        assert APNsClient.is_configured()
        token = APNsClient()._provider_token()

        header_b64, payload_b64, sig_b64 = token.split(".")
        header = json.loads(_b64url_decode(header_b64))
        payload = json.loads(_b64url_decode(payload_b64))

        assert header == {"alg": "ES256", "kid": "ABC1234567"}
        assert payload["iss"] == "TEAM123456"
        assert isinstance(payload["iat"], int)

        # Apple requires the raw r||s pair, not DER. Verify by reassembling DER.
        raw = _b64url_decode(sig_b64)
        assert len(raw) == 64, f"signature should be 64 raw bytes, got {len(raw)}"
        r = int.from_bytes(raw[:32], "big")
        s = int.from_bytes(raw[32:], "big")
        key.public_key().verify(
            encode_dss_signature(r, s),
            f"{header_b64}.{payload_b64}".encode("ascii"),
            ec.ECDSA(hashes.SHA256()),
        )


def test_provider_token_is_cached():
    with tempfile.TemporaryDirectory() as td:
        key_path = Path(td) / "AuthKey_ABC1234567.p8"
        _write_p8(key_path)
        config.APNS_KEY_PATH = str(key_path)
        config.APNS_KEY_ID = "ABC1234567"
        config.APNS_TEAM_ID = "TEAM123456"

        client = APNsClient()
        # Signing on every send would be wasteful; Apple allows an hour of reuse.
        assert client._provider_token() == client._provider_token()


def test_missing_credentials_are_reported_not_guessed():
    config.APNS_KEY_PATH = ""
    config.APNS_KEY_ID = ""
    config.APNS_TEAM_ID = ""
    assert not APNsClient.is_configured()
    try:
        APNsClient()._provider_token()
    except apns.APNsNotConfigured as exc:
        assert "HW_APNS_KEY_PATH" in str(exc)
    else:
        raise AssertionError("expected APNsNotConfigured")


def test_dead_token_detection():
    # 410 Gone and BadDeviceToken are permanent; a 503 is not.
    assert SendResult("t", ok=False, status=410).token_is_dead
    assert SendResult("t", ok=False, status=400, reason="BadDeviceToken").token_is_dead
    assert SendResult("t", ok=False, status=400, reason="Unregistered").token_is_dead
    assert not SendResult("t", ok=False, status=503, reason="ServiceUnavailable").token_is_dead
    assert not SendResult("t", ok=False, status=429, reason="TooManyRequests").token_is_dead


def _run_all():
    for fn in (
        test_provider_token_is_a_verifiable_es256_jwt,
        test_provider_token_is_cached,
        test_missing_credentials_are_reported_not_guessed,
        test_dead_token_detection,
    ):
        fn()
        print(f"  ok  {fn.__name__}")
    print("\n4 tests passed.")


if __name__ == "__main__":
    _run_all()
