"""Tests for dirdelta.textdiff.

Verifies unified diff generation for text files and the binary-file
short-circuit that avoids attempting a byte-level textual diff.
"""

from __future__ import annotations

from pathlib import Path

from dirdelta.textdiff import BINARY_DIFF_MARKER, unified_diff


class TestUnifiedDiff:
    def test_produces_unified_diff_for_differing_text_files(
        self, tmp_path: Path
    ) -> None:
        old = tmp_path / "old.txt"
        new = tmp_path / "new.txt"
        old.write_text("line one\nline two\n")
        new.write_text("line one\nline three\n")

        diff = unified_diff(old, new, "file.txt")

        assert "-line two" in diff
        assert "+line three" in diff
        assert "line one" in diff  # context line preserved

    def test_diff_header_uses_relative_path(self, tmp_path: Path) -> None:
        old = tmp_path / "old.txt"
        new = tmp_path / "new.txt"
        old.write_text("a\n")
        new.write_text("b\n")

        diff = unified_diff(old, new, "src/module.py")

        assert "a/src/module.py" in diff
        assert "b/src/module.py" in diff

    def test_identical_text_files_produce_empty_diff(self, tmp_path: Path) -> None:
        old = tmp_path / "old.txt"
        new = tmp_path / "new.txt"
        old.write_text("same content\n")
        new.write_text("same content\n")

        diff = unified_diff(old, new, "file.txt")

        assert diff == ""

    def test_binary_pair_returns_marker_instead_of_diff(self, tmp_path: Path) -> None:
        old = tmp_path / "old.bin"
        new = tmp_path / "new.bin"
        old.write_bytes(b"\x00\x01old binary")
        new.write_bytes(b"\x00\x01new binary")

        diff = unified_diff(old, new, "image.bin")

        assert diff == BINARY_DIFF_MARKER

    def test_one_binary_side_returns_marker(self, tmp_path: Path) -> None:
        old = tmp_path / "old.txt"
        new = tmp_path / "new.bin"
        old.write_text("was text\n")
        new.write_bytes(b"\x00now binary")

        diff = unified_diff(old, new, "file")

        assert diff == BINARY_DIFF_MARKER

    def test_added_lines_are_prefixed_with_plus(self, tmp_path: Path) -> None:
        old = tmp_path / "old.txt"
        new = tmp_path / "new.txt"
        old.write_text("line one\n")
        new.write_text("line one\nline two\nline three\n")

        diff = unified_diff(old, new, "file.txt")

        assert "+line two" in diff
        assert "+line three" in diff
