"""Encryption for stored Hirewheel session state.

Storage state (cookies + localStorage) is the one genuinely sensitive thing this
server holds, so it is encrypted at rest with a key that lives in the
environment rather than in the database.

This is NOT end-to-end encryption and must not be described as such: the server
has to decrypt the state in order to drive the browser, so anyone with both the
database and ``HW_SECRET_KEY`` can read a session. The encryption protects
against a leaked database file alone, nothing more.
"""

from __future__ import annotations

import os

from cryptography.fernet import Fernet, InvalidToken

_ENV_VAR = "HW_SECRET_KEY"


class MissingKey(RuntimeError):
    """Raised when the server is started without an encryption key."""


def generate_key() -> str:
    """A fresh key, for `python -m hwserver.keygen` / first-time setup."""
    return Fernet.generate_key().decode("ascii")


def _fernet() -> Fernet:
    key = os.environ.get(_ENV_VAR, "").strip()
    if not key:
        raise MissingKey(
            f"{_ENV_VAR} is not set. Generate one with:\n"
            f"    python -m hwserver.keygen\n"
            f"and set it in the environment before starting the server."
        )
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, TypeError) as exc:
        raise MissingKey(f"{_ENV_VAR} is not a valid Fernet key: {exc}") from exc


def encrypt(plaintext: str) -> bytes:
    return _fernet().encrypt(plaintext.encode("utf-8"))


def decrypt(token: bytes) -> str | None:
    """Decrypt stored state. Returns None if the key no longer matches the data,
    which we treat as 'no session' rather than crashing a scan cycle."""
    try:
        return _fernet().decrypt(token).decode("utf-8")
    except InvalidToken:
        return None
