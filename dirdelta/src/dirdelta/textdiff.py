"""Unified diffs for modified text files.

Wraps :mod:`difflib` to produce a human-readable unified diff for a pair of
modified files. Binary files are detected first (via
:func:`dirdelta.hashing.is_binary`) and reported with a placeholder marker
instead of an unreadable byte-level diff.
"""

from __future__ import annotations

import difflib
from pathlib import Path

from dirdelta import hashing

# Returned in place of a diff when at least one side is a binary file.
BINARY_DIFF_MARKER = "Binary files differ (no textual diff available)."


def unified_diff(path_a: Path, path_b: Path, relative_path: str) -> str:
    """Produce a unified diff between two versions of a file.

    Args:
        path_a: Absolute path to the "old" version.
        path_b: Absolute path to the "new" version.
        relative_path: The shared relative path, used for the diff header labels.

    Returns:
        The unified-diff text, or :data:`BINARY_DIFF_MARKER` if either file is
        binary.
    """
    if hashing.is_binary(path_a) or hashing.is_binary(path_b):
        return BINARY_DIFF_MARKER

    lines_a = path_a.read_text(errors="replace").splitlines(keepends=True)
    lines_b = path_b.read_text(errors="replace").splitlines(keepends=True)

    diff_lines = difflib.unified_diff(
        lines_a,
        lines_b,
        fromfile=f"a/{relative_path}",
        tofile=f"b/{relative_path}",
    )
    return "".join(diff_lines)
