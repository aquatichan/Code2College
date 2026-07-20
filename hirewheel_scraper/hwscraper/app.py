"""Entry point: start the scheduler and open the watch window.

Run with:  python -m hwscraper
(Log in first with:  python -m hwscraper.login)
"""

from __future__ import annotations

import tkinter as tk

from .scheduler import Scheduler
from .ui import WatchApp


def main() -> int:
    scheduler = Scheduler()
    root = tk.Tk()
    WatchApp(root, scheduler)
    scheduler.start()
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
