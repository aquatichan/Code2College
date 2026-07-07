"""Shared data models for DirDelta.

This module is the bottom of the dependency graph: it contains pure data with
no logic and no imports from other DirDelta modules. Every other module speaks
the vocabulary defined here.

The core types are:

    ChangeStatus  — the four categories a file can fall into
    FileEntry     — one file discovered by the scanner (path, size, hash)
    Comparison    — one file's classification result
    Summary       — aggregate statistics over a whole comparison
    Report        — the complete result: all comparisons plus a summary
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ChangeStatus(str, Enum):
    """The category a file falls into when two trees are compared.

    Subclasses ``str`` so values serialize cleanly to JSON as plain strings.
    """

    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    UNCHANGED = "unchanged"


@dataclass(frozen=True)
class FileEntry:
    """A single file discovered while scanning one directory tree.

    Attributes:
        relative_path: Path relative to the scanned root (the comparison key).
        size: File size in bytes.
        sha256: Hex digest of the file contents, or ``None`` if not yet hashed.
            Hashing is deferred so the scanner can stay fast; the comparator
            fills this in only when a hash is actually needed.
    """

    relative_path: str
    size: int
    sha256: Optional[str] = None


@dataclass(frozen=True)
class Comparison:
    """The result of classifying a single relative path across both trees.

    Attributes:
        relative_path: The path being reported on.
        status: Which of the four categories this file falls into.
        diff: Optional unified-diff text for modified text files. ``None`` when
            diffs are disabled, the file is unchanged, or the file is binary.
    """

    relative_path: str
    status: ChangeStatus
    diff: Optional[str] = None


@dataclass
class Summary:
    """Aggregate statistics describing a full comparison.

    Attributes:
        files_compared: Total distinct relative paths seen across both trees.
        directories: Total directories visited during scanning.
        added / removed / modified / unchanged: Per-category counts.
        extension_breakdown: Map of file extension -> count (e.g. ``{".py": 12}``).
    """

    files_compared: int = 0
    directories: int = 0
    added: int = 0
    removed: int = 0
    modified: int = 0
    unchanged: int = 0
    extension_breakdown: dict[str, int] = field(default_factory=dict)


@dataclass
class Report:
    """The complete comparison result: the source roots, every per-file
    :class:`Comparison`, and a :class:`Summary`.

    This is the single object the reporter renders — to the console or to JSON.

    Attributes:
        source_a: The "old"/left directory that was compared.
        source_b: The "new"/right directory that was compared.
        comparisons: One entry per distinct relative path.
        summary: Aggregate statistics for the comparison.
    """

    source_a: str
    source_b: str
    comparisons: list[Comparison] = field(default_factory=list)
    summary: Summary = field(default_factory=Summary)
