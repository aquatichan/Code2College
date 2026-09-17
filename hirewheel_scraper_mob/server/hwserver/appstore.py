"""Verifying App Store signed transactions (StoreKit 2).

StoreKit hands the app a `Transaction` already verified *on the device*. That is
not enough for us: the device is the thing we are trying not to trust. So the app
forwards the signed representation — a JWS — and the server checks it itself.

A StoreKit JWS is signed with a leaf certificate whose chain runs up to Apple's
root CA, and the chain travels in the token's own `x5c` header. Verification is
therefore self-contained and needs no network call and no App Store Server API
credentials:

1. decode the header and pull the x5c certificate chain
2. confirm the chain links leaf -> intermediate -> Apple root
3. confirm the leaf actually signed this token
4. confirm the payload is for *our* bundle and a product we sell

Only then is the purchase recorded.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

from . import config


class InvalidTransaction(Exception):
    """The signed transaction could not be trusted, or isn't one of ours."""


@dataclass(frozen=True)
class VerifiedPurchase:
    product_id: str
    original_transaction_id: str
    transaction_id: str
    bundle_id: str
    environment: str          # "Sandbox" or "Production", as Apple reported it
    purchased_at: datetime
    revoked: bool
    signature_verified: bool

    @property
    def interval_seconds(self) -> int:
        return config.PRODUCTS[self.product_id]


def _b64url(segment: str) -> bytes:
    return base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))


def _split(jws: str) -> tuple[dict, dict, bytes, bytes]:
    try:
        header_b64, payload_b64, signature_b64 = jws.split(".")
    except ValueError as exc:
        raise InvalidTransaction("not a JWS: expected three dot-separated parts") from exc
    try:
        header = json.loads(_b64url(header_b64))
        payload = json.loads(_b64url(payload_b64))
    except (ValueError, json.JSONDecodeError) as exc:
        raise InvalidTransaction(f"malformed JWS segments: {exc}") from exc
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    return header, payload, signing_input, _b64url(signature_b64)


def _certificates(header: dict) -> list[x509.Certificate]:
    chain = header.get("x5c") or []
    if not chain:
        raise InvalidTransaction("signed transaction carries no x5c certificate chain")
    try:
        return [x509.load_der_x509_certificate(base64.b64decode(c)) for c in chain]
    except Exception as exc:
        raise InvalidTransaction(f"unreadable certificate in chain: {exc}") from exc


def _root_certificate() -> x509.Certificate | None:
    if not config.APPSTORE_ROOT_CA_PATH:
        return None
    path = Path(config.APPSTORE_ROOT_CA_PATH)
    if not path.is_file():
        raise InvalidTransaction(f"Apple root CA not found at {path}")
    data = path.read_bytes()
    try:
        return x509.load_pem_x509_certificate(data)
    except ValueError:
        return x509.load_der_x509_certificate(data)


def _verify_chain(chain: list[x509.Certificate], root: x509.Certificate) -> None:
    """Each certificate must be signed by the next, ending at Apple's root."""
    full = chain + [root]
    for child, parent in zip(full, full[1:]):
        try:
            parent.public_key().verify(
                child.signature,
                child.tbs_certificate_bytes,
                ec.ECDSA(child.signature_hash_algorithm),  # type: ignore[arg-type]
            )
        except (InvalidSignature, TypeError, ValueError) as exc:
            raise InvalidTransaction(f"certificate chain does not reach Apple's root: {exc}") from exc

    now = datetime.now(timezone.utc)
    for cert in chain:
        if not (cert.not_valid_before_utc <= now <= cert.not_valid_after_utc):
            raise InvalidTransaction("a certificate in the chain is expired or not yet valid")


def _verify_signature(leaf: x509.Certificate, signing_input: bytes, signature: bytes) -> None:
    """ES256 over the JWS signing input, with the raw r||s pair Apple emits."""
    if len(signature) != 64:
        raise InvalidTransaction("signature is not a 64-byte ES256 pair")
    r = int.from_bytes(signature[:32], "big")
    s = int.from_bytes(signature[32:], "big")
    try:
        leaf.public_key().verify(  # type: ignore[union-attr]
            encode_dss_signature(r, s), signing_input, ec.ECDSA(hashes.SHA256())
        )
    except (InvalidSignature, TypeError, ValueError) as exc:
        raise InvalidTransaction(f"signature does not match the leaf certificate: {exc}") from exc


def verify_transaction(jws: str) -> VerifiedPurchase:
    """Check a StoreKit signed transaction and return what it entitles.

    Raises InvalidTransaction for anything untrusted, unknown, or not ours.
    """
    header, payload, signing_input, signature = _split(jws)

    signature_verified = False
    root = _root_certificate()
    if root is not None:
        chain = _certificates(header)
        _verify_chain(chain, root)
        _verify_signature(chain[0], signing_input, signature)
        signature_verified = True
    elif not config.ALLOW_UNVERIFIED_PURCHASES:
        raise InvalidTransaction(
            "purchase verification is not configured: set HW_APPSTORE_ROOT_CA to "
            "Apple's root certificate, or HW_ALLOW_UNVERIFIED_PURCHASES=1 for "
            "local StoreKit testing only"
        )

    # Contents must be ours regardless of who signed it.
    bundle_id = payload.get("bundleId")
    if bundle_id != config.APPSTORE_BUNDLE_ID:
        raise InvalidTransaction(f"transaction is for another app: {bundle_id!r}")

    product_id = payload.get("productId")
    if product_id not in config.PRODUCTS:
        raise InvalidTransaction(f"unknown product: {product_id!r}")

    # Sandbox transactions are real, Apple-signed, and free — TestFlight hands
    # them out to every tester. Accepting one on a production server would give
    # away every paid tier, so the environment is checked as strictly as the
    # signature.
    environment = str(payload.get("environment") or "")
    expected = config.APPSTORE_ENVIRONMENT
    if not environment:
        if expected == "production":
            raise InvalidTransaction(
                "transaction does not state its App Store environment; refusing it "
                "on a production server"
            )
        environment = "Unknown"
    elif environment.lower() != expected:
        raise InvalidTransaction(
            f"transaction is from the {environment} environment but this server "
            f"honours {expected} purchases only"
        )

    purchase_ms = payload.get("purchaseDate") or 0
    return VerifiedPurchase(
        product_id=product_id,
        original_transaction_id=str(payload.get("originalTransactionId") or ""),
        transaction_id=str(payload.get("transactionId") or ""),
        bundle_id=bundle_id,
        environment=environment,
        purchased_at=datetime.fromtimestamp(purchase_ms / 1000, tz=timezone.utc),
        # Apple sets this when a purchase is refunded or revoked by family sharing.
        revoked=bool(payload.get("revocationDate")),
        signature_verified=signature_verified,
    )
