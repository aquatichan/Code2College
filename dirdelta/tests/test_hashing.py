"""Tests for dirdelta.hashing.

Verifies SHA-256 digests match a reference implementation and that binary
detection correctly distinguishes text from binary content.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from dirdelta import hashing


class TestSha256Of:
    def test_matches_hashlib_reference(self, tmp_path: Path) -> None:
        content = b"hello world"
        file_path = tmp_path / "file.txt"
        file_path.write_bytes(content)

        assert hashing.sha256_of(file_path) == hashlib.sha256(content).hexdigest()

    def test_empty_file_matches_known_empty_digest(self, tmp_path: Path) -> None:
        file_path = tmp_path / "empty.txt"
        file_path.write_bytes(b"")

        assert hashing.sha256_of(file_path) == hashlib.sha256(b"").hexdigest()

    def test_stable_across_chunk_boundary(self, tmp_path: Path) -> None:
        # Exercise the chunked read loop by writing content that spans
        # multiple chunks (chunk size is 65536 bytes).
        content = b"x" * (hashing._CHUNK_SIZE * 2 + 137)
        file_path = tmp_path / "large.bin"
        file_path.write_bytes(content)

        assert hashing.sha256_of(file_path) == hashlib.sha256(content).hexdigest()

    def test_different_content_produces_different_digest(self, tmp_path: Path) -> None:
        file_a = tmp_path / "a.txt"
        file_b = tmp_path / "b.txt"
        file_a.write_bytes(b"content A")
        file_b.write_bytes(b"content B")

        assert hashing.sha256_of(file_a) != hashing.sha256_of(file_b)


class TestIsBinary:
    def test_text_file_is_not_binary(self, tmp_path: Path) -> None:
        file_path = tmp_path / "text.txt"
        file_path.write_text("hello, this is plain text\nwith multiple lines\n")

        assert hashing.is_binary(file_path) is False

    def test_file_with_nul_byte_is_binary(self, tmp_path: Path) -> None:
        file_path = tmp_path / "data.bin"
        file_path.write_bytes(b"\x00\x01\x02binary content")

        assert hashing.is_binary(file_path) is True

    def test_empty_file_is_not_binary(self, tmp_path: Path) -> None:
        file_path = tmp_path / "empty.txt"
        file_path.write_bytes(b"")

        assert hashing.is_binary(file_path) is False

    def test_nul_byte_beyond_sniff_window_is_not_detected(self, tmp_path: Path) -> None:
        # Documents the heuristic's known limitation: only the first
        # _BINARY_SNIFF_SIZE bytes are inspected.
        file_path = tmp_path / "sneaky.bin"
        prefix = b"a" * hashing._BINARY_SNIFF_SIZE
        file_path.write_bytes(prefix + b"\x00")

        assert hashing.is_binary(file_path) is False
