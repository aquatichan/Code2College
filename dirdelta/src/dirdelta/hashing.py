"""Hashing and binary-detection helpers.

Small, stateless utilities reused across the project. Depends only on the
standard library so it can be unit-tested in complete isolation.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

# Number of bytes read per chunk when hashing, so large files never have to be
# loaded fully into memory.
_CHUNK_SIZE = 65536

# Bytes sniffed from the start of a file to guess whether it is binary.
_BINARY_SNIFF_SIZE = 8192


def sha256_of(path: Path) -> str:
    """Return the SHA-256 hex digest of a file's contents.

    Reads the file in fixed-size chunks so memory usage stays constant
    regardless of file size.

    Args:
        path: Path to the file to hash.

    Returns:
        The lowercase hex digest string.
    """
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_binary(path: Path) -> bool:
    """Heuristically determine whether a file is binary rather than text.

    Reads a prefix of the file and treats it as binary if that prefix contains
    a NUL byte (``b"\\x00"``) — a cheap, common heuristic that avoids decoding
    the whole file.

    Args:
        path: Path to the file to inspect.

    Returns:
        ``True`` if the file appears to be binary, ``False`` if it looks like text.
    """
    with path.open("rb") as handle:
        chunk = handle.read(_BINARY_SNIFF_SIZE)
    return b"\x00" in chunk
