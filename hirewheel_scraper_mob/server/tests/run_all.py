"""`python -m tests.run_all` — every server test in one go."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

MODULES = [
    "tests.test_extractors",
    "tests.test_notifications",
    "tests.test_auth",
    "tests.test_accounts",
    "tests.test_children",
    "tests.test_profile",
    "tests.test_db",
    "tests.test_pipeline",
    "tests.test_push",
    "tests.test_api",
    "tests.test_hosting",
]

if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    failed = []
    for mod in MODULES:
        print(f"\n\033[1m{mod}\033[0m")
        proc = subprocess.run([sys.executable, "-m", mod], cwd=root)
        if proc.returncode != 0:
            failed.append(mod)
    print("\n" + "=" * 50)
    if failed:
        print("FAILED: " + ", ".join(failed))
        raise SystemExit(1)
    print(f"All {len(MODULES)} test modules passed.")
