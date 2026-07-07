"""Tests for dirdelta.reporter.

Verifies console rendering groups files under correct category headers with
accurate counts, and that JSON export produces valid, round-trippable JSON
matching the source report.
"""

from __future__ import annotations

import json
from pathlib import Path

from dirdelta.models import ChangeStatus, Comparison, Report, Summary
from dirdelta.reporter import render_console, render_json


def _sample_report() -> Report:
    return Report(
        source_a="old/",
        source_b="new/",
        comparisons=[
            Comparison(relative_path="added.txt", status=ChangeStatus.ADDED),
            Comparison(relative_path="removed.txt", status=ChangeStatus.REMOVED),
            Comparison(
                relative_path="modified.txt",
                status=ChangeStatus.MODIFIED,
                diff="--- a/modified.txt\n+++ b/modified.txt\n@@ -1 +1 @@\n-old\n+new",
            ),
            Comparison(relative_path="same.txt", status=ChangeStatus.UNCHANGED),
        ],
        summary=Summary(
            files_compared=4,
            directories=2,
            added=1,
            removed=1,
            modified=1,
            unchanged=1,
            extension_breakdown={".txt": 4},
        ),
    )


class TestRenderConsole:
    def test_includes_source_directories(self) -> None:
        output = render_console(_sample_report())

        assert "old/" in output
        assert "new/" in output

    def test_added_section_lists_added_files_with_count(self) -> None:
        output = render_console(_sample_report())

        assert "Added (1)" in output
        assert "added.txt" in output

    def test_removed_section_lists_removed_files_with_count(self) -> None:
        output = render_console(_sample_report())

        assert "Removed (1)" in output
        assert "removed.txt" in output

    def test_modified_section_lists_modified_files_with_count(self) -> None:
        output = render_console(_sample_report())

        assert "Modified (1)" in output
        assert "modified.txt" in output

    def test_unchanged_section_lists_unchanged_files_with_count(self) -> None:
        output = render_console(_sample_report())

        assert "Unchanged (1)" in output
        assert "same.txt" in output

    def test_summary_block_reflects_statistics(self) -> None:
        output = render_console(_sample_report())

        assert "Files Compared : 4" in output
        assert "Directories    : 2" in output
        assert "Added          : 1" in output
        assert "Removed        : 1" in output
        assert "Modified       : 1" in output
        assert "Unchanged      : 1" in output

    def test_diffs_excluded_by_default(self) -> None:
        output = render_console(_sample_report(), show_diffs=False)

        assert "-old" not in output
        assert "+new" not in output

    def test_diffs_included_when_requested(self) -> None:
        output = render_console(_sample_report(), show_diffs=True)

        assert "-old" in output
        assert "+new" in output

    def test_empty_report_renders_without_error(self) -> None:
        report = Report(source_a="a/", source_b="b/")

        output = render_console(report)

        assert "Added (0)" in output
        assert "Files Compared : 0" in output


class TestRenderJson:
    def test_writes_valid_json_file(self, tmp_path: Path) -> None:
        output_path = tmp_path / "report.json"

        render_json(_sample_report(), output_path)

        assert output_path.exists()
        data = json.loads(output_path.read_text())
        assert isinstance(data, dict)

    def test_json_contains_source_directories(self, tmp_path: Path) -> None:
        output_path = tmp_path / "report.json"

        render_json(_sample_report(), output_path)

        data = json.loads(output_path.read_text())
        assert data["source_a"] == "old/"
        assert data["source_b"] == "new/"

    def test_json_status_values_are_plain_strings(self, tmp_path: Path) -> None:
        output_path = tmp_path / "report.json"

        render_json(_sample_report(), output_path)

        data = json.loads(output_path.read_text())
        statuses = {c["status"] for c in data["comparisons"]}
        assert statuses == {"added", "removed", "modified", "unchanged"}

    def test_json_summary_matches_source_report(self, tmp_path: Path) -> None:
        output_path = tmp_path / "report.json"
        report = _sample_report()

        render_json(report, output_path)

        data = json.loads(output_path.read_text())
        assert data["summary"]["files_compared"] == report.summary.files_compared
        assert data["summary"]["added"] == report.summary.added
        assert data["summary"]["extension_breakdown"] == {".txt": 4}

    def test_json_preserves_all_comparisons(self, tmp_path: Path) -> None:
        output_path = tmp_path / "report.json"
        report = _sample_report()

        render_json(report, output_path)

        data = json.loads(output_path.read_text())
        assert len(data["comparisons"]) == len(report.comparisons)
        paths = {c["relative_path"] for c in data["comparisons"]}
        assert paths == {"added.txt", "removed.txt", "modified.txt", "same.txt"}
