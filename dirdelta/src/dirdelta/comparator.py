"""The comparison engine.

Given two scanned trees, produces a :class:`~dirdelta.models.Report` classifying
every distinct relative path as Added, Removed, Modified, or Unchanged.

Classification logic:

    * present only in B  -> ADDED
    * present only in A  -> REMOVED
    * present in both:
        - sizes differ            -> MODIFIED   (no hashing needed)
        - sizes equal, hashes eq  -> UNCHANGED
        - sizes equal, hashes ne  -> MODIFIED

Comparing sizes first lets us skip hashing entirely for the common case of
differently-sized files — an intentional optimization over hashing everything.
"""

from __future__ import annotations

from pathlib import Path

from dirdelta import hashing
from dirdelta.models import ChangeStatus, Comparison, Report, Summary
from dirdelta.scanner import ScanResult


def compare(
    root_a: Path,
    root_b: Path,
    scan_a: ScanResult,
    scan_b: ScanResult,
) -> Report:
    """Compare two scanned trees and build a full report.

    Args:
        root_a: The "old"/left directory root (for hashing and for the report).
        root_b: The "new"/right directory root.
        scan_a: Scan result for ``root_a``.
        scan_b: Scan result for ``root_b``.

    Returns:
        A :class:`Report` containing one :class:`Comparison` per distinct path
        and a populated :class:`Summary`.
    """
    all_paths = sorted(set(scan_a.entries) | set(scan_b.entries))
    comparisons: list[Comparison] = []

    for relative_path in all_paths:
        entry_a = scan_a.entries.get(relative_path)
        entry_b = scan_b.entries.get(relative_path)

        if entry_a is None:
            status = ChangeStatus.ADDED
        elif entry_b is None:
            status = ChangeStatus.REMOVED
        elif entry_a.size != entry_b.size:
            status = ChangeStatus.MODIFIED
        else:
            hash_a = hashing.sha256_of(root_a / relative_path)
            hash_b = hashing.sha256_of(root_b / relative_path)
            status = (
                ChangeStatus.UNCHANGED if hash_a == hash_b else ChangeStatus.MODIFIED
            )

        comparisons.append(Comparison(relative_path=relative_path, status=status))

    summary = _build_summary(comparisons, scan_a, scan_b)

    return Report(
        source_a=str(root_a),
        source_b=str(root_b),
        comparisons=comparisons,
        summary=summary,
    )


def _build_summary(
    comparisons: list[Comparison], scan_a: ScanResult, scan_b: ScanResult
) -> Summary:
    """Compute aggregate statistics (counts + extension breakdown) for a report.

    Args:
        comparisons: The classified comparisons produced by :func:`compare`.
        scan_a: Scan result for the left/old tree (for directory counts).
        scan_b: Scan result for the right/new tree (for directory counts).

    Returns:
        A populated :class:`Summary`.
    """
    summary = Summary(
        files_compared=len(comparisons),
        directories=scan_a.directory_count + scan_b.directory_count,
    )

    for comparison in comparisons:
        if comparison.status is ChangeStatus.ADDED:
            summary.added += 1
        elif comparison.status is ChangeStatus.REMOVED:
            summary.removed += 1
        elif comparison.status is ChangeStatus.MODIFIED:
            summary.modified += 1
        else:
            summary.unchanged += 1

        extension = Path(comparison.relative_path).suffix or "(no extension)"
        summary.extension_breakdown[extension] = (
            summary.extension_breakdown.get(extension, 0) + 1
        )

    return summary
