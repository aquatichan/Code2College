"""Presentation layer: render a report to the console or to JSON.

Contains no business logic — it only turns a :class:`~dirdelta.models.Report`
into output. Two renderers over one data model keeps presentation fully
decoupled from the comparison engine.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from dirdelta.models import ChangeStatus, Report

# Symbols used to prefix files in each category in the console output.
_STATUS_GLYPHS = {
    ChangeStatus.ADDED: "+",
    ChangeStatus.REMOVED: "-",
    ChangeStatus.MODIFIED: "*",
    ChangeStatus.UNCHANGED: "=",
}

# Categories rendered as itemized sections, in display order.
_ITEMIZED_STATUSES = (
    ChangeStatus.ADDED,
    ChangeStatus.REMOVED,
    ChangeStatus.MODIFIED,
    ChangeStatus.UNCHANGED,
)

_DIVIDER = "─" * 40


def render_console(report: Report, show_diffs: bool = False) -> str:
    """Render a report as grouped, human-readable console text.

    Groups files by category (Added / Removed / Modified / Unchanged), each with
    a count header, followed by a summary block of statistics.

    Args:
        report: The comparison result to render.
        show_diffs: If ``True``, include unified diffs beneath modified files.

    Returns:
        The full report as a single string ready to print.
    """
    lines: list[str] = []
    lines.append("DirDelta - Comparing")
    lines.append("")
    lines.append(f"A: {report.source_a}")
    lines.append(f"B: {report.source_b}")
    lines.append("")
    lines.append(_DIVIDER)

    by_status: dict[ChangeStatus, list] = {status: [] for status in ChangeStatus}
    for comparison in report.comparisons:
        by_status[comparison.status].append(comparison)

    for status in _ITEMIZED_STATUSES:
        items = by_status[status]
        lines.append("")
        lines.append(f"{status.value.capitalize()} ({len(items)})")
        lines.append("")
        glyph = _STATUS_GLYPHS[status]
        for comparison in items:
            lines.append(f" {glyph} {comparison.relative_path}")
            if show_diffs and comparison.diff:
                for diff_line in comparison.diff.splitlines():
                    lines.append(f"   {diff_line}")

    lines.append("")
    lines.append(_DIVIDER)
    lines.append("")
    lines.append("Summary")
    lines.append("")
    summary = report.summary
    lines.append(f"Files Compared : {summary.files_compared}")
    lines.append(f"Directories    : {summary.directories}")
    lines.append(f"Added          : {summary.added}")
    lines.append(f"Removed        : {summary.removed}")
    lines.append(f"Modified       : {summary.modified}")
    lines.append(f"Unchanged      : {summary.unchanged}")

    return "\n".join(lines)


def render_json(report: Report, output_path: Path) -> None:
    """Serialize a report to a JSON file.

    Args:
        report: The comparison result to serialize.
        output_path: Where to write the JSON document.
    """
    payload = asdict(report)
    output_path.write_text(json.dumps(payload, indent=2) + "\n")
