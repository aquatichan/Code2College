"""Tests for dirdelta.models.

Verifies the shared dataclasses and the ChangeStatus enum: JSON-friendly
string values, sensible defaults, and construction of Report/Summary.
"""

from __future__ import annotations

import dataclasses

import pytest

from dirdelta.models import ChangeStatus, Comparison, FileEntry, Report, Summary


class TestChangeStatus:
    def test_values_are_plain_lowercase_strings(self) -> None:
        assert ChangeStatus.ADDED.value == "added"
        assert ChangeStatus.REMOVED.value == "removed"
        assert ChangeStatus.MODIFIED.value == "modified"
        assert ChangeStatus.UNCHANGED.value == "unchanged"

    def test_is_a_string_subclass_for_json_serialization(self) -> None:
        # ChangeStatus(str, Enum) must behave like a str so json.dumps
        # serializes it as a plain string rather than an Enum repr.
        assert isinstance(ChangeStatus.ADDED, str)
        assert ChangeStatus.ADDED == "added"


class TestFileEntry:
    def test_defaults_to_no_hash(self) -> None:
        entry = FileEntry(relative_path="a.txt", size=10)

        assert entry.sha256 is None

    def test_is_immutable(self) -> None:
        entry = FileEntry(relative_path="a.txt", size=10)

        with pytest.raises(dataclasses.FrozenInstanceError):
            entry.size = 20  # type: ignore[misc]


class TestComparison:
    def test_defaults_to_no_diff(self) -> None:
        comparison = Comparison(relative_path="a.txt", status=ChangeStatus.ADDED)

        assert comparison.diff is None


class TestSummary:
    def test_defaults_are_all_zero(self) -> None:
        summary = Summary()

        assert summary.files_compared == 0
        assert summary.directories == 0
        assert summary.added == 0
        assert summary.removed == 0
        assert summary.modified == 0
        assert summary.unchanged == 0
        assert summary.extension_breakdown == {}

    def test_extension_breakdown_defaults_are_independent(self) -> None:
        # Guards against a shared mutable default (a classic dataclass bug).
        summary_a = Summary()
        summary_b = Summary()

        summary_a.extension_breakdown[".py"] = 1

        assert summary_b.extension_breakdown == {}


class TestReport:
    def test_defaults_to_empty_comparisons_and_fresh_summary(self) -> None:
        report = Report(source_a="old/", source_b="new/")

        assert report.comparisons == []
        assert report.summary == Summary()

    def test_comparisons_default_is_independent_per_instance(self) -> None:
        report_a = Report(source_a="old/", source_b="new/")
        report_b = Report(source_a="old/", source_b="new/")

        report_a.comparisons.append(
            Comparison(relative_path="a.txt", status=ChangeStatus.ADDED)
        )

        assert report_b.comparisons == []
