"""Regenerate the app icon set from the vector source.

    cd ios/design && python3 make_icons.py            # palette A (default)
    cd ios/design && python3 make_icons.py B_teal     # or another palette

Needs Playwright's Chromium (already installed for the server) and Pillow.
The art is drawn as vector in logo.py, so every size is rendered fresh rather
than scaled from a raster.
"""

import sys
from pathlib import Path

from PIL import Image

from logo import icon_svg, render
from palettes import DARK_A, PALETTES

OUT = Path(__file__).resolve().parent.parent / "Hirewatch/Assets.xcassets/AppIcon.appiconset"
SCALE = 0.82  # margin inside the iOS rounded mask

TINTED = dict(cap="#FFFFFF", braces="#C9C9C9", outline="#000000",
              eye="#FFFFFF", pupil="#000000", dots="#FFFFFF")

if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "A_indigo"
    light = PALETTES[name]
    render(icon_svg(light, scale=SCALE), str(OUT / "AppIcon.png"), 1024)
    render(icon_svg(DARK_A, scale=SCALE), str(OUT / "AppIcon-Dark.png"), 1024)
    render(icon_svg(TINTED, scale=SCALE, background=None), str(OUT / "AppIcon-Tinted.png"), 1024, transparent=True)
    Image.open(OUT / "AppIcon-Tinted.png").convert("LA").save(OUT / "AppIcon-Tinted.png")
    print(f"icons written to {OUT} using palette {name}")
