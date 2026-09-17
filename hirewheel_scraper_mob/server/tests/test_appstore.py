"""App Store purchase verification.

This is the only thing standing between "the app says I paid" and a real
entitlement, so the tests build an actual certificate chain and sign real tokens
rather than stubbing the crypto out.
"""

from __future__ import annotations

import base64
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.x509.oid import NameOID

from hwserver import appstore, config
from hwserver.appstore import InvalidTransaction, verify_transaction

BUNDLE = "com.aaronqin.HirewheelWatch"
PRODUCT = "com.aaronqin.HirewheelWatch.interval6h"


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _make_cert(subject: str, key, issuer_name, issuer_key, *, ca: bool, days=(-1, 365)):
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, subject)])
    now = datetime.now(timezone.utc)
    builder = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(issuer_name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now + timedelta(days=days[0]))
        .not_valid_after(now + timedelta(days=days[1]))
        .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True)
    )
    return builder.sign(issuer_key, hashes.SHA256()), name


class Chain:
    """A stand-in for Apple's root -> intermediate -> leaf hierarchy."""

    def __init__(self):
        self.root_key = ec.generate_private_key(ec.SECP256R1())
        self.root, root_name = self._self_signed("Test Root", self.root_key)

        self.inter_key = ec.generate_private_key(ec.SECP256R1())
        self.inter, inter_name = _make_cert(
            "Test Intermediate", self.inter_key, root_name, self.root_key, ca=True
        )
        self.leaf_key = ec.generate_private_key(ec.SECP256R1())
        self.leaf, _ = _make_cert("Test Leaf", self.leaf_key, inter_name, self.inter_key, ca=False)

    @staticmethod
    def _self_signed(subject, key):
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, subject)])
        now = datetime.now(timezone.utc)
        cert = (
            x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(days=1))
            .not_valid_after(now + timedelta(days=365))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .sign(key, hashes.SHA256())
        )
        return cert, name

    def write_root(self, path: Path) -> Path:
        path.write_bytes(self.root.public_bytes(serialization.Encoding.PEM))
        return path

    def sign(self, payload: dict, *, signing_key=None) -> str:
        der = [
            base64.b64encode(c.public_bytes(serialization.Encoding.DER)).decode("ascii")
            for c in (self.leaf, self.inter)
        ]
        header = _b64url(json.dumps({"alg": "ES256", "x5c": der}).encode())
        body = _b64url(json.dumps(payload).encode())
        signing_input = f"{header}.{body}".encode("ascii")
        key = signing_key or self.leaf_key
        raw = key.sign(signing_input, ec.ECDSA(hashes.SHA256()))
        r, s = decode_dss_signature(raw)
        sig = _b64url(r.to_bytes(32, "big") + s.to_bytes(32, "big"))
        return f"{header}.{body}.{sig}"


def _payload(**overrides) -> dict:
    base = {
        "bundleId": BUNDLE,
        "productId": PRODUCT,
        "transactionId": "2000000001",
        "originalTransactionId": "2000000001",
        "environment": "Sandbox",
        "purchaseDate": int(datetime.now(timezone.utc).timestamp() * 1000),
    }
    base.update(overrides)
    return base


def _configure(chain: Chain, tmp: Path, *, allow_unverified=False, environment="sandbox"):
    config.APPSTORE_BUNDLE_ID = BUNDLE
    config.APPSTORE_ROOT_CA_PATH = str(chain.write_root(tmp / "root.pem"))
    config.ALLOW_UNVERIFIED_PURCHASES = allow_unverified
    config.APPSTORE_ENVIRONMENT = environment


def test_valid_transaction_is_accepted():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        chain = Chain()
        _configure(chain, Path(td))
        result = verify_transaction(chain.sign(_payload()))
        assert result.product_id == PRODUCT
        assert result.interval_seconds == 6 * 3600
        assert result.signature_verified is True
        assert result.revoked is False


def test_tampered_payload_is_rejected():
    """The whole point: change the product after signing and it must not verify."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        chain = Chain()
        _configure(chain, Path(td))
        jws = chain.sign(_payload())
        header, _body, sig = jws.split(".")
        forged = _b64url(json.dumps(
            _payload(productId="com.aaronqin.HirewheelWatch.interval1h")
        ).encode())
        try:
            verify_transaction(f"{header}.{forged}.{sig}")
        except InvalidTransaction as exc:
            assert "signature" in str(exc).lower()
        else:
            raise AssertionError("a tampered transaction was accepted")


def test_chain_from_another_root_is_rejected():
    """A self-signed chain an attacker made must not pass as Apple's."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        real, attacker = Chain(), Chain()
        _configure(real, Path(td))
        try:
            verify_transaction(attacker.sign(_payload()))
        except InvalidTransaction as exc:
            assert "root" in str(exc).lower() or "chain" in str(exc).lower()
        else:
            raise AssertionError("a foreign certificate chain was accepted")


def test_other_apps_purchase_is_rejected():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        chain = Chain()
        _configure(chain, Path(td))
        try:
            verify_transaction(chain.sign(_payload(bundleId="com.someone.else")))
        except InvalidTransaction as exc:
            assert "another app" in str(exc)
        else:
            raise AssertionError("a purchase from another app was accepted")


def test_unknown_product_is_rejected():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        chain = Chain()
        _configure(chain, Path(td))
        try:
            verify_transaction(chain.sign(_payload(productId="com.aaronqin.free.lunch")))
        except InvalidTransaction as exc:
            assert "unknown product" in str(exc)
        else:
            raise AssertionError("an unknown product was accepted")


def test_refund_is_surfaced():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        chain = Chain()
        _configure(chain, Path(td))
        revoked_at = int(datetime.now(timezone.utc).timestamp() * 1000)
        result = verify_transaction(chain.sign(_payload(revocationDate=revoked_at)))
        assert result.revoked is True


def test_verification_is_required_unless_explicitly_disabled():
    """With no root configured the server must refuse, not quietly trust."""
    config.APPSTORE_ROOT_CA_PATH = ""
    config.ALLOW_UNVERIFIED_PURCHASES = False
    chain = Chain()
    try:
        verify_transaction(chain.sign(_payload()))
    except InvalidTransaction as exc:
        assert "not configured" in str(exc)
    else:
        raise AssertionError("an unverified purchase was accepted by default")


def test_local_storekit_testing_can_be_opted_into():
    config.APPSTORE_ROOT_CA_PATH = ""
    config.ALLOW_UNVERIFIED_PURCHASES = True
    config.APPSTORE_BUNDLE_ID = BUNDLE
    chain = Chain()
    result = verify_transaction(chain.sign(_payload()))
    # Accepted, but honestly labelled as unproven.
    assert result.signature_verified is False
    config.ALLOW_UNVERIFIED_PURCHASES = False


def test_sandbox_transaction_cannot_unlock_a_production_server():
    """The TestFlight replay attack.

    Apple signs sandbox transactions with a genuine certificate chain, so the
    signature check passes for them. TestFlight purchases are free and handed to
    every tester, so without an environment check a production server could be
    unlocked for nothing.
    """
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        chain = Chain()
        _configure(chain, Path(td), environment="production")
        jws = chain.sign(_payload(environment="Sandbox"))
        try:
            verify_transaction(jws)
        except InvalidTransaction as exc:
            assert "Sandbox" in str(exc) and "production" in str(exc)
        else:
            raise AssertionError("a free sandbox purchase unlocked a production server")


def test_production_transaction_is_accepted_in_production():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        chain = Chain()
        _configure(chain, Path(td), environment="production")
        result = verify_transaction(chain.sign(_payload(environment="Production")))
        assert result.environment == "Production"


def test_sandbox_is_accepted_on_a_sandbox_server():
    """TestFlight testing still has to work when the server expects sandbox."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        chain = Chain()
        _configure(chain, Path(td), environment="sandbox")
        result = verify_transaction(chain.sign(_payload(environment="Sandbox")))
        assert result.environment == "Sandbox"


def test_missing_environment_is_refused_in_production():
    """An old or hand-made payload must not sneak past by omitting the field."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        chain = Chain()
        _configure(chain, Path(td), environment="production")
        payload = _payload()
        del payload["environment"]
        try:
            verify_transaction(chain.sign(payload))
        except InvalidTransaction as exc:
            assert "environment" in str(exc)
        else:
            raise AssertionError("a transaction with no stated environment was accepted")


def _run_all():
    for fn in (
        test_valid_transaction_is_accepted,
        test_tampered_payload_is_rejected,
        test_chain_from_another_root_is_rejected,
        test_other_apps_purchase_is_rejected,
        test_unknown_product_is_rejected,
        test_refund_is_surfaced,
        test_verification_is_required_unless_explicitly_disabled,
        test_local_storekit_testing_can_be_opted_into,
        test_sandbox_transaction_cannot_unlock_a_production_server,
        test_production_transaction_is_accepted_in_production,
        test_sandbox_is_accepted_on_a_sandbox_server,
        test_missing_environment_is_refused_in_production,
    ):
        fn()
        print(f"  ok  {fn.__name__}")
    print("\n12 tests passed.")


if __name__ == "__main__":
    _run_all()
