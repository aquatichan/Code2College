"""Render PortfolioData into an HTML portfolio site and/or an HTML CV."""

from __future__ import annotations

import datetime as _dt
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .github_client import PortfolioData

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"

# A small, stable color per common language for the language bar.
LANG_COLORS = {
    "Python": "#3572A5",
    "JavaScript": "#f1e05a",
    "TypeScript": "#3178c6",
    "HTML": "#e34c26",
    "CSS": "#563d7c",
    "Java": "#b07219",
    "C++": "#f34b7d",
    "C": "#555555",
    "C#": "#178600",
    "Go": "#00ADD8",
    "Rust": "#dea584",
    "Ruby": "#701516",
    "PHP": "#4F5D95",
    "Swift": "#F05138",
    "Kotlin": "#A97BFF",
    "Shell": "#89e051",
    "Dart": "#00B4AB",
    "Vue": "#41b883",
    "Jupyter Notebook": "#DA5B0B",
}
DEFAULT_LANG_COLOR = "#8b949e"


def _lang_color(name: str) -> str:
    return LANG_COLORS.get(name, DEFAULT_LANG_COLOR)


class Builder:
    def __init__(self, data: PortfolioData, beautifier=None):
        """`beautifier`: optional callable(css: str, doc_kind: str) -> str | None
        (typically AIEnhancer.beautify_css) used to AI-polish the <style> block."""
        self.data = data
        self.beautifier = beautifier
        self.env = Environment(
            loader=FileSystemLoader(str(TEMPLATE_DIR)),
            autoescape=select_autoescape(["html", "xml"]),
        )
        self.env.filters["lang_color"] = _lang_color

    def _maybe_beautify(self, html: str, doc_kind: str) -> str:
        """Run the beautifier over the document's first <style> block, if set."""
        if not self.beautifier:
            return html
        start = html.find("<style>")
        end = html.find("</style>")
        if start == -1 or end == -1:
            return html
        css = html[start + len("<style>"):end]
        improved = self.beautifier(css, doc_kind)
        if not improved:
            return html
        print(f"Applied AI CSS beautify to {doc_kind}.")
        return html[:start + len("<style>")] + improved + html[end:]

    def _context(self) -> dict:
        return {
            "d": self.data,
            "profile": self.data.profile,
            "generated_on": _dt.date.today().strftime("%B %d, %Y"),
        }

    def render_html(self, out_path: Path) -> Path:
        template = self.env.get_template("portfolio.html.j2")
        html = self._maybe_beautify(template.render(**self._context()), "portfolio")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(html, encoding="utf-8")
        return out_path
