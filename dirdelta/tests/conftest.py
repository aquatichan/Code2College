"""Shared pytest fixtures for the DirDelta test suite.

Fixtures here build temporary directory trees so comparison behavior can be
exercised against real filesystem structures rather than mocks — DirDelta is
fundamentally a filesystem tool, so its tests should touch the filesystem.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Mapping

import pytest

# A tree spec maps relative-path strings to contents. ``str`` contents are
# written as UTF-8 text; ``bytes`` contents are written as raw binary — this
# lets a single fixture build both text and binary fixtures.
TreeSpec = Mapping[str, "str | bytes"]
TreeFactory = Callable[[TreeSpec], Path]


@pytest.fixture
def tree_factory(tmp_path: Path) -> TreeFactory:
    """Return a helper that materializes a directory tree from a dict.

    The helper maps ``{relative_path: contents}`` into real files under a fresh
    subdirectory of ``tmp_path``, creating parent directories as needed. Each
    call creates a new, independently named subdirectory so a single test can
    build multiple trees (e.g. "old" and "new") without collisions.

    Example::

        old = tree_factory({"a.txt": "hello", "src/main.py": "print(1)"})
        new = tree_factory({"a.txt": "hello", "src/main.py": "print(2)"})
    """
    counter = {"n": 0}

    def _make(spec: TreeSpec) -> Path:
        counter["n"] += 1
        root = tmp_path / f"tree{counter['n']}"
        root.mkdir()

        for relative_path, contents in spec.items():
            file_path = root / relative_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(contents, bytes):
                file_path.write_bytes(contents)
            else:
                file_path.write_text(contents)

        return root

    return _make
