"""DirDelta — a command-line directory comparison utility.

DirDelta recursively compares two directory trees and produces an organized
change report categorizing every file as Added, Removed, Modified, or Unchanged,
along with summary statistics and optional unified diffs.

The package is organized into single-responsibility modules:

    models      — shared dataclasses and enums (the common vocabulary)
    scanner     — recursive directory traversal
    hashing     — SHA-256 helpers and binary-file detection
    ignore      — ignore-pattern matching
    comparator  — the classification engine
    textdiff    — unified diffs for modified text files
    reporter    — terminal rendering and JSON export
    cli         — argument parsing and workflow orchestration
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
