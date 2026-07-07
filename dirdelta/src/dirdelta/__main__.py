"""Module entry point so DirDelta can be run as ``python -m dirdelta``.

Delegates to :func:`dirdelta.cli.main` and propagates its exit code.
"""

import sys

from dirdelta.cli import main

if __name__ == "__main__":
    sys.exit(main())
