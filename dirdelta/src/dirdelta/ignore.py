"""Ignore-pattern matching.

Owns the glob/fnmatch semantics for excluding files and directories such as
``.git``, ``__pycache__``, ``.DS_Store``, or ``*.pyc``. Kept separate from the
scanner so pattern matching can be tested independently and so the scanner
stays a pure directory walker.
"""

from __future__ import annotations

from fnmatch import fnmatch
from typing import Iterable


class IgnoreMatcher:
    """Compiles a set of ignore patterns and tests paths against them.

    Patterns are matched against both a path's individual components (so
    ``.git`` excludes any ``.git`` directory anywhere in the tree) and against
    the full relative path (so globs like ``build/*`` work). Matching uses
    :mod:`fnmatch` semantics.
    """

    def __init__(self, patterns: Iterable[str] = ()) -> None:
        """Store the ignore patterns.

        Args:
            patterns: Glob-style patterns, e.g. ``[".git", "__pycache__", "*.pyc"]``.
        """
        self._patterns: tuple[str, ...] = tuple(patterns)

    def should_ignore(self, relative_path: str) -> bool:
        """Return whether ``relative_path`` matches any ignore pattern.

        A path is ignored if any individual path component matches a pattern
        (so a pattern like ``.git`` excludes that directory no matter how deep
        it is nested) or if the full relative path matches a pattern (so globs
        like ``build/*`` or ``src/**/*.pyc``-style path globs also work).

        Args:
            relative_path: A path relative to the scanned root, using ``/`` as
                the separator.

        Returns:
            ``True`` if the path should be excluded from comparison.
        """
        if not self._patterns:
            return False

        parts = relative_path.split("/")
        for pattern in self._patterns:
            if fnmatch(relative_path, pattern):
                return True
            if any(fnmatch(part, pattern) for part in parts):
                return True
        return False
