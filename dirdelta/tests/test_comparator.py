"""Tests for dirdelta.comparator.

Verifies the classification engine: identical trees yield only Unchanged,
files unique to one side are Added/Removed, differing files are Modified
(including the same-size-different-content case that forces a hash
comparison), and Summary statistics are correct.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dirdelta.comparator import compare
from dirdelta.models import ChangeStatus
from dirdelta.scanner import scan

if TYPE_CHECKING:
    from tests.conftest import TreeFactory


def _status_map(report):
    """Helper: relative_path -> ChangeStatus for easy assertions."""
    return {c.relative_path: c.status for c in report.comparisons}


class TestCompare:
    def test_identical_trees_are_all_unchanged(self, tree_factory: "TreeFactory") -> None:
        old = tree_factory({"a.txt": "same", "src/main.py": "print(1)"})
        new = tree_factory({"a.txt": "same", "src/main.py": "print(1)"})

        report = compare(old, new, scan(old), scan(new))

        statuses = _status_map(report)
        assert statuses == {
            "a.txt": ChangeStatus.UNCHANGED,
            "src/main.py": ChangeStatus.UNCHANGED,
        }

    def test_empty_trees_produce_empty_report(self, tree_factory: "TreeFactory") -> None:
        old = tree_factory({})
        new = tree_factory({})

        report = compare(old, new, scan(old), scan(new))

        assert report.comparisons == []
        assert report.summary.files_compared == 0

    def test_file_only_in_new_is_added(self, tree_factory: "TreeFactory") -> None:
        old = tree_factory({"a.txt": "A"})
        new = tree_factory({"a.txt": "A", "b.txt": "B"})

        report = compare(old, new, scan(old), scan(new))

        assert _status_map(report)["b.txt"] == ChangeStatus.ADDED

    def test_file_only_in_old_is_removed(self, tree_factory: "TreeFactory") -> None:
        old = tree_factory({"a.txt": "A", "gone.txt": "bye"})
        new = tree_factory({"a.txt": "A"})

        report = compare(old, new, scan(old), scan(new))

        assert _status_map(report)["gone.txt"] == ChangeStatus.REMOVED

    def test_different_size_content_is_modified(self, tree_factory: "TreeFactory") -> None:
        old = tree_factory({"f.txt": "short"})
        new = tree_factory({"f.txt": "a much longer replacement string"})

        report = compare(old, new, scan(old), scan(new))

        assert _status_map(report)["f.txt"] == ChangeStatus.MODIFIED

    def test_same_size_different_content_is_modified(
        self, tree_factory: "TreeFactory"
    ) -> None:
        # Both strings are 5 bytes — this can only be caught by hashing,
        # not by the size short-circuit. Exercises the hash-comparison path.
        old = tree_factory({"f.txt": "abcde"})
        new = tree_factory({"f.txt": "edcba"})

        report = compare(old, new, scan(old), scan(new))

        assert _status_map(report)["f.txt"] == ChangeStatus.MODIFIED

    def test_same_size_same_content_is_unchanged(
        self, tree_factory: "TreeFactory"
    ) -> None:
        old = tree_factory({"f.txt": "abcde"})
        new = tree_factory({"f.txt": "abcde"})

        report = compare(old, new, scan(old), scan(new))

        assert _status_map(report)["f.txt"] == ChangeStatus.UNCHANGED

    def test_nested_directory_structures_are_classified_correctly(
        self, tree_factory: "TreeFactory"
    ) -> None:
        old = tree_factory(
            {
                "src/pkg/mod.py": "old content",
                "src/pkg/keep.py": "unchanged",
                "src/pkg/gone.py": "removed",
            }
        )
        new = tree_factory(
            {
                "src/pkg/mod.py": "new content!!",
                "src/pkg/keep.py": "unchanged",
                "src/pkg/added.py": "added",
            }
        )

        report = compare(old, new, scan(old), scan(new))

        statuses = _status_map(report)
        assert statuses["src/pkg/mod.py"] == ChangeStatus.MODIFIED
        assert statuses["src/pkg/keep.py"] == ChangeStatus.UNCHANGED
        assert statuses["src/pkg/gone.py"] == ChangeStatus.REMOVED
        assert statuses["src/pkg/added.py"] == ChangeStatus.ADDED

    def test_mixed_changes_produce_correct_summary_counts(
        self, tree_factory: "TreeFactory"
    ) -> None:
        old = tree_factory(
            {"same.txt": "x", "changed.txt": "old", "removed.txt": "gone"}
        )
        new = tree_factory(
            {"same.txt": "x", "changed.txt": "new value", "added.txt": "new"}
        )

        report = compare(old, new, scan(old), scan(new))
        summary = report.summary

        assert summary.files_compared == 4
        assert summary.added == 1
        assert summary.removed == 1
        assert summary.modified == 1
        assert summary.unchanged == 1

    def test_extension_breakdown_counts_by_suffix(
        self, tree_factory: "TreeFactory"
    ) -> None:
        old = tree_factory({"a.py": "1", "b.py": "2", "c.txt": "3"})
        new = tree_factory({"a.py": "1", "b.py": "2", "c.txt": "3"})

        report = compare(old, new, scan(old), scan(new))

        assert report.summary.extension_breakdown == {".py": 2, ".txt": 1}

    def test_file_without_extension_uses_placeholder_bucket(
        self, tree_factory: "TreeFactory"
    ) -> None:
        old = tree_factory({"Makefile": "all:"})
        new = tree_factory({"Makefile": "all:"})

        report = compare(old, new, scan(old), scan(new))

        assert report.summary.extension_breakdown == {"(no extension)": 1}

    def test_report_records_source_roots(self, tree_factory: "TreeFactory") -> None:
        old = tree_factory({})
        new = tree_factory({})

        report = compare(old, new, scan(old), scan(new))

        assert report.source_a == str(old)
        assert report.source_b == str(new)
