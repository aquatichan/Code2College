"""Tkinter front-end: a persistent 'Hirewheel Watch' window.

Shows a running feed of what's new/changed/removed each cycle. Each changed
page's screenshot renders inline in its card. Runs on the main thread and
receives updates from the Scheduler's event queue via ``after`` polling.
"""

from __future__ import annotations

import queue
import tkinter as tk
from datetime import datetime
from tkinter import ttk

from . import config
from .diff import PageDiff
from .pipeline import CycleResult
from .scheduler import Scheduler, UIEvent

_PAGE_LABELS = {p.key: p.label for p in config.PAGES}

# Palette
BG = "#0f1720"
CARD = "#1b2430"
FG = "#e6edf3"
MUTED = "#8b98a5"
GREEN = "#3fb950"
YELLOW = "#d2be22"
RED = "#f85149"
ACCENT = "#4b9fff"
POLL_MS = 500
MAX_CYCLES = 15       # cap feed history so memory/scroll stay bounded on long runs
IMG_MAX_WIDTH = 660   # inline screenshots are downscaled to fit this width


def _fmt_local(dt: datetime) -> str:
    return dt.astimezone().strftime("%b %d, %I:%M %p")


class ScrollableFrame(ttk.Frame):
    """A vertically scrollable container of stacked cards."""

    def __init__(self, master):
        super().__init__(master)
        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        vsb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.inner = tk.Frame(self.canvas, bg=BG)
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._win, width=e.width))
        # Mouse wheel (macOS/Windows/Linux).
        self.canvas.bind_all("<MouseWheel>", self._on_wheel)
        self.canvas.bind_all("<Button-4>", lambda e: self.canvas.yview_scroll(-1, "units"))
        self.canvas.bind_all("<Button-5>", lambda e: self.canvas.yview_scroll(1, "units"))

    def _on_wheel(self, event):
        delta = -1 if event.delta > 0 else 1
        self.canvas.yview_scroll(delta, "units")


class WatchApp:
    def __init__(self, root: tk.Tk, scheduler: Scheduler):
        self.root = root
        self.scheduler = scheduler
        self._screenshots: dict[str, str] = {}
        self._cycle_groups: list[tk.Frame] = []  # one container per rendered cycle

        root.title("Hirewheel Watch")
        root.geometry("720x820")
        root.configure(bg=BG)

        self._build_header()
        self._build_feed()
        self._add_placeholder()

        root.after(POLL_MS, self._poll)
        root.protocol("WM_DELETE_WINDOW", self._on_close)

    # -- layout ---------------------------------------------------------------
    def _build_header(self):
        bar = tk.Frame(self.root, bg=CARD)
        bar.pack(fill="x", side="top")

        title = tk.Label(bar, text="💼  Hirewheel Watch", bg=CARD, fg=FG,
                         font=("Courier New", 16, "bold"))
        title.pack(side="left", padx=14, pady=12)

        self.scan_btn = tk.Button(bar, text="Scan now", font=("Courier New", 12), 
                                  command=self.scheduler.trigger_now,
                                  bg=ACCENT, fg=CARD, relief="flat", padx=12, pady=4,
                                  activebackground="#3d86e0", cursor="hand2")
        self.scan_btn.pack(side="right", padx=14)

        self.status = tk.Label(self.root, text="Starting…", bg=BG, fg=MUTED,
                               anchor="w", font=("Courier New", 11))
        self.status.pack(fill="x", padx=16, pady=(8, 0))

        self.banner = tk.Label(self.root, text="", bg=RED, fg="white", anchor="w",
                               font=("Courier New", 11, "bold"), padx=12, pady=8)
        # packed only when needed

    def _build_feed(self):
        self.feed = ScrollableFrame(self.root)
        self.feed.pack(fill="both", expand=True, padx=12, pady=12)

    # -- feed helpers ---------------------------------------------------------
    def _add_placeholder(self):
        self._placeholder = tk.Label(
            self.feed.inner,
            text="Watching your Hirewheel pages.\nNew opportunities and updates will appear here.",
            bg=BG, fg=MUTED, font=("Courier New", 12), justify="center", pady=40,
        )
        self._placeholder.pack(fill="x")

    def _clear_placeholder(self):
        if getattr(self, "_placeholder", None) is not None:
            self._placeholder.destroy()
            self._placeholder = None

    def _card(self, parent) -> tk.Frame:
        card = tk.Frame(parent, bg=CARD, bd=0)
        card.pack(fill="x", pady=6, ipady=2)
        return card

    # -- event loop -----------------------------------------------------------
    def _poll(self):
        try:
            while True:
                try:
                    ev = self.scheduler.events.get_nowait()
                except queue.Empty:
                    break
                self._handle(ev)
        finally:
            # Always keep polling, even if a handler raised (Tk logs the error).
            self.root.after(POLL_MS, self._poll)

    def _handle(self, ev: UIEvent):
        if ev.type == "status":
            self.status.config(text=ev.message, fg=MUTED)
        elif ev.type == "auth_needed":
            self._show_banner(ev.message)
        elif ev.type == "error":
            self.status.config(text=ev.message, fg=RED)
        elif ev.type == "cycle":
            self._hide_banner()
            self._render_cycle(ev.payload)

    def _show_banner(self, text: str):
        self.banner.config(text="⚠  " + text)
        self.banner.pack(fill="x", before=self.feed, padx=0, pady=(6, 0))

    def _hide_banner(self):
        self.banner.pack_forget()

    # -- rendering ------------------------------------------------------------
    def _render_cycle(self, result: CycleResult):
        stamp = _fmt_local(result.started_at)
        changed = result.changed_pages
        if not changed:
            self.status.config(text=f"Last scan: {stamp} — no changes.", fg=MUTED)
            return

        self._clear_placeholder()
        self._screenshots.update(result.screenshots)

        # Everything from this cycle goes in one container we can prune later.
        group = tk.Frame(self.feed.inner, bg=BG)
        group.pack(fill="x")
        self._cycle_groups.append(group)

        header = self._card(group)
        tk.Label(header, text=f"● {stamp} — {result.total_changes} update(s)",
                 bg=CARD, fg=ACCENT, font=("Courier New", 12, "bold"),
                 anchor="w").pack(fill="x", padx=12, pady=6)

        for pdiff in changed:
            self._render_page_diff(group, pdiff)

        # Bound history so a long-running watcher doesn't grow without limit.
        while len(self._cycle_groups) > MAX_CYCLES:
            self._cycle_groups.pop(0).destroy()

        self.status.config(text=f"Last scan: {stamp} — {result.total_changes} update(s) found.",
                           fg=GREEN)
        # Scroll to reveal the newest updates once the layout settles.
        self.root.after_idle(lambda: self.feed.canvas.yview_moveto(1.0))

    def _render_page_diff(self, parent, pdiff: PageDiff):
        card = self._card(parent)
        label = _PAGE_LABELS.get(pdiff.page_key, pdiff.page_key)

        top = tk.Frame(card, bg=CARD)
        top.pack(fill="x", padx=12, pady=(8, 2))
        tk.Label(top, text=label, bg=CARD, fg=FG, font=("Courier New", 13, "bold"),
                 anchor="w").pack(side="left")

        for it in pdiff.added:
            self._line(card, "+ NEW", GREEN, it.title, self._item_details(it.fields))
        for ch in pdiff.changed:
            self._line(card, "✎ CHANGED", YELLOW, ch.item.title, self._delta_lines(ch.changed_fields))
        for it in pdiff.removed:
            self._line(card, "- REMOVED", MUTED, it.title, self._item_details(it.fields))

        # Show the page's screenshot inline, under the item lines.
        self._render_screenshot_inline(card, pdiff.page_key)

    def _line(self, parent, tag, color, title, details):
        row = tk.Frame(parent, bg=CARD)
        row.pack(fill="x", padx=12, pady=3)
        tk.Label(row, text=tag, bg=CARD, fg=color, font=("Courier New", 10, "bold"),
                 width=11, anchor="w").pack(side="left", anchor="n")
        text = tk.Frame(row, bg=CARD)
        text.pack(side="left", fill="x", expand=True)
        tk.Label(text, text=title, bg=CARD, fg=FG, font=("Courier New", 11),
                 anchor="w", justify="left", wraplength=500).pack(fill="x")
        for line in details:
            tk.Label(text, text=line, bg=CARD, fg=MUTED, font=("Courier New", 9),
                     anchor="w", justify="left", wraplength=500).pack(fill="x")

    # Field keys that read as a sentence vs. short attributes shown on one meta line.
    _DESC_KEYS = ("body", "goal", "description", "tagline", "detail")
    _META_KEYS = ("section", "status", "when", "date", "due", "category", "platforms", "xp", "price")
    _LIST_KEYS = ("tags", "pills")

    @classmethod
    def _item_details(cls, fields: dict) -> list[str]:
        """Turn an item's captured fields into readable lines under its title."""
        lines: list[str] = []
        for key in cls._DESC_KEYS:
            if fields.get(key):
                lines.append(str(fields[key]))
                break
        meta = [str(fields[k]) for k in cls._META_KEYS if fields.get(k)]
        for k in cls._LIST_KEYS:
            v = fields.get(k)
            if v:
                meta.append(", ".join(map(str, v)) if isinstance(v, (list, tuple)) else str(v))
        if meta:
            lines.append("  ·  ".join(meta))
        link = fields.get("href") or fields.get("action_url")
        if link:
            lines.append(f"→ {link}")
        return lines

    @staticmethod
    def _delta_lines(changed_fields: dict) -> list[str]:
        """Human-readable 'field: old → new' lines for a changed item."""
        def fmt(v):
            return str(v) if v not in (None, "") else "—"

        lines: list[str] = []
        for key, (old, new) in changed_fields.items():
            if key == "signature":            # opaque whole-page hash — don't show it
                lines.append("page content changed")
                continue
            lines.append(f"{key}: {fmt(old)} → {fmt(new)}")
        return lines or ["updated"]

    def _render_screenshot_inline(self, parent, page_key: str):
        """Display the page's screenshot inline at the bottom of its card."""
        path = self._screenshots.get(page_key)
        if not path:
            return
        try:
            img = tk.PhotoImage(file=path)
        except Exception:
            return  # unreadable/unsupported image — just skip it
        # Scale full-page shots down to fit the card width (Tk only does integer
        # subsampling, so this snaps to the nearest whole-number factor).
        factor = max(1, img.width() // IMG_MAX_WIDTH)
        if factor > 1:
            img = img.subsample(factor, factor)

        holder = tk.Frame(parent, bg=CARD)
        holder.pack(fill="x", padx=12, pady=(4, 12))
        lbl = tk.Label(holder, image=img, bg=CARD, bd=0)
        lbl.image = img  # keep the ref on the widget so it dies with the card
        lbl.pack(anchor="w")

    def _on_close(self):
        self.status.config(text="Stopping…")
        self.scheduler.stop()
        self.root.destroy()
