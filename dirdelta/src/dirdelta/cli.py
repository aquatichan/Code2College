"""Command-line interface and workflow orchestration.

The conductor at the top of the dependency graph. It parses arguments,
validates the two directory paths, builds the ignore matcher, and drives the
pipeline: scan -> compare -> (optional) diff -> report. It contains
orchestration, not algorithms.

Usage::

    python -m dirdelta OLD NEW [--diff] [--ignore PATTERN ...] [--json PATH]
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path
from typing import Optional, Sequence

from dirdelta import comparator, reporter, scanner, textdiff
from dirdelta.ignore import IgnoreMatcher
from dirdelta.models import ChangeStatus

# Process exit codes (script-friendly, git-diff style).
EXIT_NO_DIFFERENCES = 0
EXIT_DIFFERENCES_FOUND = 1
EXIT_USAGE_ERROR = 2

# Ignore patterns applied even when the user supplies none, since a directory
# comparison tool is far less useful by default if it trips over VCS/build
# artifacts. Users can still pass their own --ignore patterns on top of these.
_DEFAULT_IGNORE_PATTERNS = (".git", "__pycache__", "*.pyc", ".DS_Store")


def build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser for the ``dirdelta`` command.

    Returns:
        A configured :class:`argparse.ArgumentParser`.
    """
    parser = argparse.ArgumentParser(
        prog="dirdelta",
        description="Compare two directory trees and report the differences.",
    )
    parser.add_argument("old", type=Path, help="the 'old' / left directory")
    parser.add_argument("new", type=Path, help="the 'new' / right directory")
    parser.add_argument(
        "--diff",
        action="store_true",
        help="show unified diffs for modified text files",
    )
    parser.add_argument(
        "--ignore",
        action="append",
        default=[],
        metavar="PATTERN",
        help=(
            "glob pattern to ignore (repeatable); added to the defaults "
            f"({', '.join(_DEFAULT_IGNORE_PATTERNS)})"
        ),
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=None,
        metavar="PATH",
        help="export the full report as JSON to PATH",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Program entry point.

    Parses arguments and runs the full comparison pipeline.

    Args:
        argv: Argument list (defaults to ``sys.argv[1:]`` when ``None``).

    Returns:
        A process exit code: ``0`` if the trees are identical, ``1`` if any
        differences were found, ``2`` on usage errors.
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    old_dir: Path = args.old
    new_dir: Path = args.new

    if not old_dir.is_dir():
        print(f"dirdelta: error: not a directory: {old_dir}", file=sys.stderr)
        return EXIT_USAGE_ERROR
    if not new_dir.is_dir():
        print(f"dirdelta: error: not a directory: {new_dir}", file=sys.stderr)
        return EXIT_USAGE_ERROR

    ignore = IgnoreMatcher(list(_DEFAULT_IGNORE_PATTERNS) + list(args.ignore))

    scan_a = scanner.scan(old_dir, ignore)
    scan_b = scanner.scan(new_dir, ignore)

    report = comparator.compare(old_dir, new_dir, scan_a, scan_b)

    if args.diff:
        updated_comparisons = []
        for comparison in report.comparisons:
            if comparison.status is ChangeStatus.MODIFIED:
                diff_text = textdiff.unified_diff(
                    old_dir / comparison.relative_path,
                    new_dir / comparison.relative_path,
                    comparison.relative_path,
                )
                comparison = replace(comparison, diff=diff_text)
            updated_comparisons.append(comparison)
        report.comparisons = updated_comparisons

    print(reporter.render_console(report, show_diffs=args.diff))

    if args.json is not None:
        reporter.render_json(report, args.json)

    has_differences = (
        report.summary.added > 0
        or report.summary.removed > 0
        or report.summary.modified > 0
    )
    return EXIT_DIFFERENCES_FOUND if has_differences else EXIT_NO_DIFFERENCES
