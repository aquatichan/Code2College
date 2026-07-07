"""End-to-end tests for dirdelta.cli.

Drives the full pipeline through main() exactly as a user would invoke it,
verifying exit codes, JSON export, ignore-pattern handling, and diff output
via captured stdout — not by reaching into internal collaborators.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from dirdelta.cli import (
    EXIT_DIFFERENCES_FOUND,
    EXIT_NO_DIFFERENCES,
    EXIT_USAGE_ERROR,
    main,
)

if TYPE_CHECKING:
    from tests.conftest import TreeFactory


class TestExitCodes:
    def test_identical_directories_exit_zero(
        self, tree_factory: "TreeFactory", capsys: pytest.CaptureFixture
    ) -> None:
        old = tree_factory({"a.txt": "same", "b.txt": "also same"})
        new = tree_factory({"a.txt": "same", "b.txt": "also same"})

        exit_code = main([str(old), str(new)])

        assert exit_code == EXIT_NO_DIFFERENCES

    def test_differences_found_exits_one(
        self, tree_factory: "TreeFactory", capsys: pytest.CaptureFixture
    ) -> None:
        old = tree_factory({"a.txt": "old content"})
        new = tree_factory({"a.txt": "new content"})

        exit_code = main([str(old), str(new)])

        assert exit_code == EXIT_DIFFERENCES_FOUND

    def test_added_file_alone_exits_one(
        self, tree_factory: "TreeFactory", capsys: pytest.CaptureFixture
    ) -> None:
        old = tree_factory({"a.txt": "x"})
        new = tree_factory({"a.txt": "x", "new.txt": "new"})

        exit_code = main([str(old), str(new)])

        assert exit_code == EXIT_DIFFERENCES_FOUND

    def test_missing_old_directory_exits_two(
        self, tree_factory: "TreeFactory", tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        new = tree_factory({"a.txt": "x"})
        missing = tmp_path / "does_not_exist"

        exit_code = main([str(missing), str(new)])

        assert exit_code == EXIT_USAGE_ERROR

    def test_missing_new_directory_exits_two(
        self, tree_factory: "TreeFactory", tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        old = tree_factory({"a.txt": "x"})
        missing = tmp_path / "does_not_exist"

        exit_code = main([str(old), str(missing)])

        assert exit_code == EXIT_USAGE_ERROR

    def test_file_path_instead_of_directory_exits_two(
        self, tree_factory: "TreeFactory", capsys: pytest.CaptureFixture
    ) -> None:
        old = tree_factory({"a.txt": "x"})
        new = tree_factory({"a.txt": "x"})
        a_file = old / "a.txt"

        exit_code = main([str(a_file), str(new)])

        assert exit_code == EXIT_USAGE_ERROR

    def test_usage_error_writes_to_stderr(
        self, tree_factory: "TreeFactory", tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        new = tree_factory({"a.txt": "x"})
        missing = tmp_path / "does_not_exist"

        main([str(missing), str(new)])

        captured = capsys.readouterr()
        assert captured.err != ""


class TestConsoleOutput:
    def test_prints_report_to_stdout(
        self, tree_factory: "TreeFactory", capsys: pytest.CaptureFixture
    ) -> None:
        old = tree_factory({"a.txt": "x"})
        new = tree_factory({"a.txt": "x", "b.txt": "new"})

        main([str(old), str(new)])

        captured = capsys.readouterr()
        assert "Added (1)" in captured.out
        assert "b.txt" in captured.out


class TestDefaultIgnorePatterns:
    def test_git_directory_is_ignored_by_default(
        self, tree_factory: "TreeFactory", capsys: pytest.CaptureFixture
    ) -> None:
        old = tree_factory({"a.txt": "x", ".git/HEAD": "ref"})
        new = tree_factory({"a.txt": "x"})

        exit_code = main([str(old), str(new)])

        # Only .git differs (which is ignored), so trees should be identical.
        assert exit_code == EXIT_NO_DIFFERENCES

    def test_pycache_is_ignored_by_default(
        self, tree_factory: "TreeFactory", capsys: pytest.CaptureFixture
    ) -> None:
        old = tree_factory({"a.py": "x", "__pycache__/a.pyc": "compiled"})
        new = tree_factory({"a.py": "x"})

        exit_code = main([str(old), str(new)])

        assert exit_code == EXIT_NO_DIFFERENCES


class TestCustomIgnorePatterns:
    def test_custom_ignore_pattern_excludes_matching_files(
        self, tree_factory: "TreeFactory", capsys: pytest.CaptureFixture
    ) -> None:
        old = tree_factory({"a.txt": "x", "notes.log": "old log"})
        new = tree_factory({"a.txt": "x", "notes.log": "different log"})

        exit_code = main([str(old), str(new), "--ignore", "*.log"])

        assert exit_code == EXIT_NO_DIFFERENCES

    def test_without_ignore_flag_the_log_difference_is_detected(
        self, tree_factory: "TreeFactory", capsys: pytest.CaptureFixture
    ) -> None:
        old = tree_factory({"a.txt": "x", "notes.log": "old log"})
        new = tree_factory({"a.txt": "x", "notes.log": "different log"})

        exit_code = main([str(old), str(new)])

        assert exit_code == EXIT_DIFFERENCES_FOUND

    def test_custom_ignore_is_additive_to_defaults(
        self, tree_factory: "TreeFactory", capsys: pytest.CaptureFixture
    ) -> None:
        old = tree_factory({"a.txt": "x", ".git/HEAD": "ref", "b.log": "1"})
        new = tree_factory({"a.txt": "x", "b.log": "2"})

        exit_code = main([str(old), str(new), "--ignore", "*.log"])

        # .git ignored by default, *.log ignored via --ignore: nothing left to differ.
        assert exit_code == EXIT_NO_DIFFERENCES


class TestDiffFlag:
    def test_diff_flag_includes_unified_diff_in_output(
        self, tree_factory: "TreeFactory", capsys: pytest.CaptureFixture
    ) -> None:
        old = tree_factory({"a.txt": "line one\n"})
        new = tree_factory({"a.txt": "line one\nline two\n"})

        main([str(old), str(new), "--diff"])

        captured = capsys.readouterr()
        assert "+line two" in captured.out

    def test_without_diff_flag_no_diff_text_shown(
        self, tree_factory: "TreeFactory", capsys: pytest.CaptureFixture
    ) -> None:
        old = tree_factory({"a.txt": "line one\n"})
        new = tree_factory({"a.txt": "line one\nline two\n"})

        main([str(old), str(new)])

        captured = capsys.readouterr()
        assert "+line two" not in captured.out

    def test_diff_flag_shows_binary_marker_for_binary_files(
        self, tree_factory: "TreeFactory", capsys: pytest.CaptureFixture
    ) -> None:
        old = tree_factory({"img.bin": b"\x00\x01old"})
        new = tree_factory({"img.bin": b"\x00\x01new"})

        main([str(old), str(new), "--diff"])

        captured = capsys.readouterr()
        assert "Binary files differ" in captured.out


class TestJsonExport:
    def test_json_flag_writes_report_file(
        self, tree_factory: "TreeFactory", tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        old = tree_factory({"a.txt": "x"})
        new = tree_factory({"a.txt": "x", "b.txt": "new"})
        report_path = tmp_path / "report.json"

        main([str(old), str(new), "--json", str(report_path)])

        assert report_path.exists()

    def test_json_report_contents_match_comparison(
        self, tree_factory: "TreeFactory", tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        old = tree_factory({"a.txt": "x"})
        new = tree_factory({"a.txt": "x", "b.txt": "new"})
        report_path = tmp_path / "report.json"

        main([str(old), str(new), "--json", str(report_path)])

        data = json.loads(report_path.read_text())
        assert data["summary"]["added"] == 1
        added_paths = {
            c["relative_path"] for c in data["comparisons"] if c["status"] == "added"
        }
        assert added_paths == {"b.txt"}

    def test_no_json_file_written_without_flag(
        self, tree_factory: "TreeFactory", tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        old = tree_factory({"a.txt": "x"})
        new = tree_factory({"a.txt": "y"})
        report_path = tmp_path / "should_not_exist.json"

        main([str(old), str(new)])

        assert not report_path.exists()


class TestEmptyDirectories:
    def test_two_empty_directories_are_identical(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        old = tmp_path / "old"
        new = tmp_path / "new"
        old.mkdir()
        new.mkdir()

        exit_code = main([str(old), str(new)])

        assert exit_code == EXIT_NO_DIFFERENCES
