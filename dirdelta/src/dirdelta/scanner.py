"""Recursive directory scanning.

Walks a single directory tree and records every (non-ignored) file as a
:class:`~dirdelta.models.FileEntry`, keyed by its path relative to the root.
The scanner knows nothing about *comparison* — it only answers "what is in
this tree?". It accepts an :class:`~dirdelta.ignore.IgnoreMatcher` so it can
prune ignored subtrees while walking rather than collecting-then-discarding.

Returning a ``dict`` keyed by relative path lets the comparator perform its
set difference in O(n) over the keys.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from dirdelta.ignore import IgnoreMatcher
from dirdelta.models import FileEntry


class ScanResult:
    """The outcome of scanning one tree.

    Attributes:
        entries: Map of relative path -> :class:`FileEntry`.
        directory_count: Number of directories visited (for statistics).
    """

    def __init__(self) -> None:
        self.entries: dict[str, FileEntry] = {}
        self.directory_count: int = 0


def scan(root: Path, ignore: Optional[IgnoreMatcher] = None) -> ScanResult:
    """Recursively scan ``root`` and collect its files.

    Sizes are recorded eagerly (cheap, from the filesystem); content hashes are
    left as ``None`` and filled in later by the comparator only when needed.

    Ignored directories are pruned in place during the walk, so their subtrees
    are never descended into (as opposed to collecting everything and
    filtering afterward).

    Args:
        root: The directory to scan.
        ignore: Optional matcher; ignored paths (and their subtrees) are skipped.

    Returns:
        A :class:`ScanResult` with entries and a directory count.
    """
    result = ScanResult()

    for dirpath, dirnames, filenames in os.walk(root):
        current_dir = Path(dirpath)
        result.directory_count += 1

        if ignore is not None:
            dirnames[:] = [
                name
                for name in dirnames
                if not ignore.should_ignore(
                    (current_dir / name).relative_to(root).as_posix()
                )
            ]

        for filename in filenames:
            file_path = current_dir / filename
            relative_path = file_path.relative_to(root).as_posix()

            if ignore is not None and ignore.should_ignore(relative_path):
                continue

            size = file_path.stat().st_size
            result.entries[relative_path] = FileEntry(
                relative_path=relative_path, size=size
            )

    return result
