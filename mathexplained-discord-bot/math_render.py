"""Rendering helpers for the MathEXplained bot.

- LaTeX is rendered via the CodeCogs remote PNG endpoint (no local TeX install needed).
- Asymptote is rendered by shelling out to the `asy` binary if it is installed on the host.
"""

import asyncio
import os
import shutil
import ssl
import tempfile
from urllib.parse import quote

import aiohttp
import certifi

_ssl_context = ssl.create_default_context(cafile=certifi.where())

# CodeCogs renders LaTeX (math mode) to a PNG. \dpi{300} gives a crisp, high-res image.
_CODECOGS_URL = "https://latex.codecogs.com/png.image?"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

# White text on an opaque black chip so it stays readable in both Discord dark mode
# (most users) and light mode, rather than the CodeCogs default of black-on-transparent
# which disappears on dark backgrounds. Note: \bg_white (underscore form) is required —
# \bg{white} is silently ignored by CodeCogs and leaves the background transparent.
_STYLE_PREFIX = r"\dpi{300}\bg_white\color{Black}"


class RenderError(Exception):
    """Raised when a render fails for a reason worth showing the user."""


async def render_latex(latex: str) -> bytes:
    """Render a LaTeX expression to PNG bytes via CodeCogs. Raises RenderError on failure."""
    latex = latex.strip()
    if not latex:
        raise RenderError("No LaTeX provided.")

    url = _CODECOGS_URL + _STYLE_PREFIX + quote(latex)
    connector = aiohttp.TCPConnector(ssl=_ssl_context)
    try:
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    raise RenderError(f"Render service returned HTTP {resp.status}.")
                data = await resp.read()
    except aiohttp.ClientError as exc:
        raise RenderError(f"Could not reach the render service: {exc}") from exc

    if not data.startswith(_PNG_MAGIC):
        # CodeCogs returns a (non-PNG) error image / text when the LaTeX is invalid.
        raise RenderError("Invalid LaTeX — the expression could not be rendered.")
    return data


async def render_asymptote(source: str) -> bytes | None:
    """Render Asymptote source to PNG bytes.

    Returns None if the `asy` binary is not installed on the host.
    Raises RenderError if asy runs but fails to compile the source.
    """
    source = source.strip()
    if not source:
        raise RenderError("No Asymptote source provided.")

    if shutil.which("asy") is None:
        return None

    tmpdir = tempfile.mkdtemp(prefix="asy_")
    in_path = os.path.join(tmpdir, "input.asy")
    out_stem = os.path.join(tmpdir, "output")
    out_path = out_stem + ".png"
    try:
        with open(in_path, "w") as f:
            f.write(source)

        proc = await asyncio.create_subprocess_exec(
            "asy", "-f", "png", "-o", out_stem, in_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=tmpdir,
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0 or not os.path.exists(out_path):
            detail = stderr.decode(errors="replace").strip() or "unknown error"
            # Keep the message short enough to fit in a Discord reply.
            raise RenderError(f"Asymptote compile error:\n{detail[:1500]}")

        with open(out_path, "rb") as f:
            return f.read()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


async def render_math_text(text: str, *, as_answer: bool = False) -> bytes:
    """Render a problem statement or answer as a LaTeX-styled image.

    Reuses the CodeCogs path so /submitproblem and /renderlatex share one renderer.
    `as_answer` is accepted for call-site clarity; both are rendered the same way.
    """
    return await render_latex(text)
