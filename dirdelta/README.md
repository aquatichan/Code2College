# 📈📉 DirDelta

A command-line directory comparison utility that produces a clean, organized
change report between two directory trees. DirDelta recursively compares two
directories and classifies every file as **Added**, **Removed**, **Modified**,
or **Unchanged**, then presents the result as a readable console report or a
machine-readable JSON export — complete with summary statistics and optional
unified diffs.

Built entirely on the Python standard library, with zero runtime dependencies.

## Motivation

Comparing two directory trees sounds trivial until you actually need to do it
well. Naive approaches — diffing `ls -R` output, or recursively `diff`-ing
every file pair — are slow, noisy, and don't scale to real project sizes.
They also tend to choke on binary files, VCS metadata, and build artifacts
that have no business being compared in the first place.

DirDelta was built to be the tool an engineer would actually reach for when
comparing backups, verifying a deployment matches its source, auditing a
release against the previous one, or reviewing what changed between two
snapshots of a codebase. It favors:

- **Correctness over cleverness** — content is verified with SHA-256 hashing,
  not just file size or timestamps.
- **Signal over noise** — ignore patterns and a size short-circuit keep the
  comparison focused on files that matter.
- **Composability** — JSON export means DirDelta's output can feed into other
  tooling, not just a human reading a terminal.

## Key Features

- **Recursive directory comparison** — walks both trees and matches files by
  relative path.
- **Content-accurate change detection** — SHA-256 hashing determines whether
  files actually differ, with a size short-circuit that skips hashing
  whenever file sizes already differ.
- **Four-way classification** — every file is sorted into Added, Removed,
  Modified, or Unchanged.
- **Unified text diffs** — modified text files get a `difflib`-generated
  unified diff (`--diff`); binary files are detected automatically and shown
  with a clear marker instead of a garbled byte-level diff.
- **Ignore patterns** — exclude paths like `.git`, `__pycache__`, `*.pyc`, or
  `.DS_Store`; sensible defaults are applied automatically and your own
  `--ignore` patterns are layered on top.
- **Summary statistics** — total files compared, directories visited,
  per-category counts, and a file-extension breakdown.
- **JSON report export** — the full comparison result serializes cleanly to
  JSON for downstream tooling or CI pipelines.
- **Zero dependencies** — pure Python standard library, nothing to install
  beyond Python itself.

## Architecture Overview

DirDelta is organized into single-responsibility modules under
`src/dirdelta/`, each with a single, testable concern:

| Module          | Responsibility                                              |
| --------------- | ------------------------------------------------------------|
| `models.py`     | Shared dataclasses and the `ChangeStatus` enum               |
| `scanner.py`    | Recursively walks a tree into `{relative_path: FileEntry}`   |
| `hashing.py`    | SHA-256 hashing and binary-file detection                    |
| `ignore.py`     | Ignore-pattern matching (`IgnoreMatcher`)                    |
| `comparator.py` | Classification engine — builds the `Report`                  |
| `textdiff.py`   | Unified diffs for modified text files                        |
| `reporter.py`   | Console rendering and JSON export                            |
| `cli.py`        | Argument parsing and pipeline orchestration                  |

**Execution flow:**

```
cli
 ├─ validate old/new paths, build the ignore matcher
 ├─ scanner.scan(old) / scanner.scan(new)   → two trees of FileEntry
 ├─ comparator.compare(...)                 → classify every path
 │     (hashes are only computed when file sizes match)
 ├─ textdiff.unified_diff(...)              → optional, per modified file
 └─ reporter.render_console(...) / render_json(...)
```

Each stage depends only on the ones beneath it — `models` sits at the bottom
with no dependencies, `cli` sits at the top and orchestrates everything else.
This keeps every module independently testable and makes the codebase easy to
extend without cross-cutting changes.

## Installation

Requires **Python 3.9+**.

```bash
git clone https://github.com/aquatichan/Code2College.git
cd Code2College/dirdelta

# Editable install — exposes the `dirdelta` command:
pip install -e .

# For development (adds pytest):
pip install -e ".[dev]"
```

No installation is required to run it directly from source:

```bash
python -m dirdelta OLD_DIR NEW_DIR
```

## Command-Line Usage

```bash
dirdelta OLD_DIR NEW_DIR [OPTIONS]
```

| Option              | Description                                                        |
| -------------------- | ------------------------------------------------------------------ |
| `--diff`             | Show unified diffs for modified text files                        |
| `--ignore PATTERN`   | Ignore matching files/directories (repeatable)                    |
| `--json PATH`        | Export the full comparison report as JSON to `PATH`               |
| `-h`, `--help`       | Show usage information                                            |

Default ignore patterns (`.git`, `__pycache__`, `*.pyc`, `.DS_Store`) are
always applied; any patterns passed via `--ignore` are added on top of them.

**Exit codes** (script-friendly, similar to `diff`):

| Code | Meaning                          |
| ---- | --------------------------------- |
| `0`  | No differences found              |
| `1`  | Differences were found            |
| `2`  | Usage error (e.g. invalid path)   |

### Examples

```bash
# Basic comparison
dirdelta project_old/ project_new/

# Show unified diffs for modified text files
dirdelta project_old/ project_new/ --diff

# Exclude additional patterns beyond the built-in defaults
dirdelta project_old/ project_new/ --ignore "*.log" --ignore "build/*"

# Export the full report as JSON
dirdelta project_old/ project_new/ --json report.json
```

## Example Output

```text
Comparing

A: project_old
B: project_new

────────────────────────────────

Added (1)

 + docs/setup.md

Removed (1)

 - legacy.py

Modified (1)

 * src/main.py
   --- a/src/main.py
   +++ b/src/main.py
   @@ -1,2 +1,2 @@
    def main():
   -    print('v1')
   +    print('v2')

Unchanged (2)

 = README.md
 = config.json

────────────────────────────────

Summary

Files Compared : 5
Directories    : 5
Added          : 1
Removed        : 1
Modified       : 1
Unchanged      : 2
```

The JSON export (`--json report.json`) contains the same information in a
structured form:

```json
{
  "source_a": "project_old",
  "source_b": "project_new",
  "comparisons": [
    { "relative_path": "legacy.py", "status": "removed", "diff": null },
    { "relative_path": "docs/setup.md", "status": "added", "diff": null },
    { "relative_path": "src/main.py", "status": "modified", "diff": "--- a/src/main.py\n+++ b/src/main.py\n..." }
  ],
  "summary": {
    "files_compared": 5,
    "directories": 5,
    "added": 1,
    "removed": 1,
    "modified": 1,
    "unchanged": 2,
    "extension_breakdown": { ".md": 2, ".json": 1, ".py": 2 }
  }
}
```

## Testing

DirDelta has an 87-test pytest suite covering every module — normal behavior
and edge cases alike, including identical/empty/nested directory trees,
same-size-but-different-content files (which force the hash-comparison path),
ignore-pattern matching, binary detection, unified diffs, JSON round-tripping,
and all three CLI exit codes.

```bash
pip install -e ".[dev]"
pytest
```

Test files live in `tests/`, one per source module, with shared fixtures
(most notably a `tree_factory` for building temporary directory trees) in
`tests/conftest.py`.

## Project Structure

```text
dirdelta/
├── pyproject.toml            # packaging, dependencies, pytest config
├── requirements.txt          # empty — stdlib only
├── requirements-dev.txt      # pytest
├── README.md
├── src/
│   └── dirdelta/
│       ├── __init__.py
│       ├── __main__.py       # `python -m dirdelta` entry point
│       ├── models.py
│       ├── scanner.py
│       ├── hashing.py
│       ├── ignore.py
│       ├── comparator.py
│       ├── textdiff.py
│       ├── reporter.py
│       └── cli.py
└── tests/
    ├── conftest.py
    ├── test_models.py
    ├── test_scanner.py
    ├── test_hashing.py
    ├── test_ignore.py
    ├── test_comparator.py
    ├── test_textdiff.py
    ├── test_reporter.py
    └── test_cli.py
```
