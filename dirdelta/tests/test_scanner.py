"""Tests for dirdelta.scanner.

Verifies recursive traversal, relative-path correctness, ignore-pattern
pruning, and directory counting.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from dirdelta.ignore import IgnoreMatcher
from dirdelta.scanner import scan

if TYPE_CHECKING:
    from tests.conftest import TreeFactory


class TestScan:
    def test_empty_directory_yields_no_entries(self, tmp_path: Path) -> None:
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        result = scan(empty_dir)

        assert result.entries == {}
        assert result.directory_count == 1

    def test_flat_directory_records_every_file(self, tree_factory: TreeFactory) -> None:
        root = tree_factory({"a.txt": "A", "b.txt": "B", "c.txt": "C"})

        result = scan(root)

        assert set(result.entries) == {"a.txt", "b.txt", "c.txt"}

    def test_nested_directories_are_traversed_recursively(
        self, tree_factory: TreeFactory
    ) -> None:
        root = tree_factory(
            {
                "top.txt": "top",
                "src/main.py": "main",
                "src/utils/helpers.py": "helpers",
                "src/utils/deep/nested/file.txt": "deep",
            }
        )

        result = scan(root)

        assert set(result.entries) == {
            "top.txt",
            "src/main.py",
            "src/utils/helpers.py",
            "src/utils/deep/nested/file.txt",
        }

    def test_directory_count_reflects_directories_visited(
        self, tree_factory: TreeFactory
    ) -> None:
        root = tree_factory({"a/b/c/file.txt": "x"})

        result = scan(root)

        # root itself, a, a/b, a/b/c = 4 directories.
        assert result.directory_count == 4

    def test_file_size_is_recorded(self, tree_factory: TreeFactory) -> None:
        root = tree_factory({"file.txt": "12345"})

        result = scan(root)

        assert result.entries["file.txt"].size == 5

    def test_hash_is_not_computed_eagerly(self, tree_factory: TreeFactory) -> None:
        root = tree_factory({"file.txt": "content"})

        result = scan(root)

        assert result.entries["file.txt"].sha256 is None

    def test_ignored_file_is_excluded(self, tree_factory: TreeFactory) -> None:
        root = tree_factory({"keep.txt": "keep", "skip.pyc": "skip"})
        ignore = IgnoreMatcher(["*.pyc"])

        result = scan(root, ignore)

        assert set(result.entries) == {"keep.txt"}

    def test_ignored_directory_subtree_is_pruned(
        self, tree_factory: TreeFactory
    ) -> None:
        root = tree_factory(
            {
                "keep.txt": "keep",
                ".git/HEAD": "ref: refs/heads/main",
                ".git/objects/abc123": "blob",
                "__pycache__/module.pyc": "compiled",
            }
        )
        ignore = IgnoreMatcher([".git", "__pycache__"])

        result = scan(root, ignore)

        assert set(result.entries) == {"keep.txt"}

    def test_ignoring_directory_reduces_directory_count(
        self, tree_factory: TreeFactory
    ) -> None:
        root = tree_factory({"keep.txt": "keep", ".git/objects/deep/file": "x"})

        unfiltered = scan(root)
        filtered = scan(root, IgnoreMatcher([".git"]))

        assert filtered.directory_count < unfiltered.directory_count

    def test_relative_paths_use_forward_slashes(
        self, tree_factory: TreeFactory
    ) -> None:
        root = tree_factory({"a/b/file.txt": "x"})

        result = scan(root)

        assert "a/b/file.txt" in result.entries
        assert "\\" not in next(iter(result.entries))
