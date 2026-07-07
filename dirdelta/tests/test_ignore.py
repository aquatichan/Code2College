"""Tests for dirdelta.ignore.

Verifies IgnoreMatcher's pattern matching against both individual path
components (so a bare name like ".git" matches anywhere in the tree) and
full relative paths (so path-shaped globs also work).
"""

from __future__ import annotations

from dirdelta.ignore import IgnoreMatcher


class TestIgnoreMatcher:
    def test_empty_matcher_ignores_nothing(self) -> None:
        matcher = IgnoreMatcher([])

        assert matcher.should_ignore("anything.txt") is False
        assert matcher.should_ignore("deeply/nested/path.py") is False

    def test_bare_name_matches_top_level_component(self) -> None:
        matcher = IgnoreMatcher([".git"])

        assert matcher.should_ignore(".git") is True

    def test_bare_name_matches_nested_component(self) -> None:
        matcher = IgnoreMatcher([".git"])

        assert matcher.should_ignore("project/.git") is True
        assert matcher.should_ignore("a/b/c/.git") is True

    def test_bare_name_does_not_match_substring(self) -> None:
        matcher = IgnoreMatcher(["git"])

        # fnmatch semantics: "git" should not match "mygit" or ".github".
        assert matcher.should_ignore("mygit") is False
        assert matcher.should_ignore(".github") is False

    def test_extension_glob_matches_by_suffix(self) -> None:
        matcher = IgnoreMatcher(["*.pyc"])

        assert matcher.should_ignore("module.pyc") is True
        assert matcher.should_ignore("pkg/module.pyc") is True
        assert matcher.should_ignore("module.py") is False

    def test_unmatched_path_is_not_ignored(self) -> None:
        matcher = IgnoreMatcher([".git", "__pycache__", "*.pyc"])

        assert matcher.should_ignore("src/main.py") is False
        assert matcher.should_ignore("README.md") is False

    def test_multiple_patterns_are_all_checked(self) -> None:
        matcher = IgnoreMatcher([".git", "__pycache__", "*.pyc", ".DS_Store"])

        assert matcher.should_ignore("__pycache__") is True
        assert matcher.should_ignore("nested/__pycache__") is True
        assert matcher.should_ignore(".DS_Store") is True
        assert matcher.should_ignore("assets/.DS_Store") is True

    def test_full_path_glob_matches_whole_relative_path(self) -> None:
        matcher = IgnoreMatcher(["build/*"])

        assert matcher.should_ignore("build/output.o") is True
        assert matcher.should_ignore("src/build/output.o") is False
