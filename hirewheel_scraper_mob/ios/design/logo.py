"""Vector redraw of the logo, parameterised by palette.

Geometry is measured from the supplied 1000x1000 image, in that coordinate space.
Cut-outs (the gap between the mortarboard and its crown, the crown's curved lower
edge) are real SVG masks rather than shapes painted in the background colour, so
the same art works on any background — light, dark, or transparent.
"""

GEOMETRY = """
  <defs>
    <mask id="board-cut" maskUnits="userSpaceOnUse" x="0" y="0" width="1000" height="1000">
      <rect width="1000" height="1000" fill="#fff"/>
      <ellipse cx="502" cy="480" rx="277" ry="230" fill="#000"/>
      <rect x="225" y="480" width="554" height="200" fill="#000"/>
    </mask>
    <mask id="crown-cut" maskUnits="userSpaceOnUse" x="0" y="0" width="1000" height="1000">
      <rect width="1000" height="1000" fill="#fff"/>
      <circle cx="503" cy="933" r="515" fill="#000"/>
    </mask>
  </defs>

  <!-- mortarboard -->
  <polygon points="42,322 500,106 958,322 502,543" fill="{cap}" mask="url(#board-cut)"/>
  <ellipse cx="503" cy="520" rx="258" ry="245" fill="{cap}" mask="url(#crown-cut)"/>

  <!-- tassel -->
  <rect x="110.5" y="352" width="28" height="92" rx="4" fill="{cap}"/>
  <circle cx="124.5" cy="465" r="33" fill="{cap}"/>
  <path d="M106 486 L143 486 L155 545 Q124.5 550 94 545 Z" fill="{cap}"/>

  <!-- braces -->
  <g fill="none" stroke="{braces}" stroke-width="27" stroke-linecap="round" stroke-linejoin="round">
    <path d="M361 487 C326 487 313 500 313 532 L313 618 C313 645 302 657 279 659 C302 661 313 673 313 700 L313 788 C313 818 326 830 361 830"/>
    <path d="M646 487 C681 487 695 500 695 532 L695 618 C695 645 706 657 729 659 C706 661 695 673 695 700 L695 788 C695 818 681 830 646 830"/>
  </g>

  <!-- googly eyes -->
  <g stroke="{outline}" stroke-width="7">
    <ellipse cx="433.5" cy="612" rx="57" ry="78" fill="{eye}"/>
    <ellipse cx="572.5" cy="612" rx="57" ry="78" fill="{eye}"/>
  </g>
  <ellipse cx="407" cy="611" rx="26" ry="38" fill="{pupil}"/>
  <ellipse cx="546" cy="611" rx="27" ry="38" fill="{pupil}"/>
  <circle cx="397" cy="593" r="7.5" fill="{eye}"/>
  <circle cx="536" cy="593" r="7.5" fill="{eye}"/>

  <!-- dots -->
  <g fill="{dots}">
    <circle cx="426" cy="778" r="19.5"/>
    <circle cx="504" cy="778" r="19.5"/>
    <circle cx="582" cy="778" r="19.5"/>
  </g>
"""


def art(p: dict) -> str:
    """The logo alone, in its native 1000x1000 space."""
    return GEOMETRY.format(**p)


def icon_svg(p: dict, size: int = 1024, scale: float = 0.86, background: str | None = "auto") -> str:
    """A square app icon: background + logo centred with iOS-friendly margins."""
    # content bbox in source space: x 42..958, y 106..847
    cx, cy = 500, 476
    s = size / 1000 * scale
    tx = size / 2 - cx * s
    ty = size / 2 - cy * s + size * 0.012   # nudge down a hair: the cap reads top-heavy
    bg = ""
    if background:
        top, bottom = p["bg_top"], p["bg_bottom"]
        bg = f'''<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stop-color="{top}"/><stop offset="1" stop-color="{bottom}"/>
          </linearGradient></defs>
          <rect width="{size}" height="{size}" fill="url(#bg)"/>'''
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
            f'viewBox="0 0 {size} {size}">{bg}'
            f'<g transform="translate({tx:.2f} {ty:.2f}) scale({s:.5f})">{art(p)}</g></svg>')


def render(svg: str, out_png: str, size: int, transparent: bool = False) -> None:
    """Rasterise with Chromium at 2x, then downsample — cleaner edges than 1x."""
    from playwright.sync_api import sync_playwright
    from PIL import Image
    html = (f'<html><body style="margin:0;background:transparent">'
            f'<div style="width:{size}px;height:{size}px">{svg}</div></body></html>')
    tmp = out_png + ".2x.png"
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": size, "height": size}, device_scale_factor=2)
        pg.set_content(html)
        pg.screenshot(path=tmp, omit_background=transparent, clip={"x": 0, "y": 0, "width": size, "height": size})
        b.close()
    im = Image.open(tmp).convert("RGBA").resize((size, size), Image.LANCZOS)
    if not transparent:
        im = im.convert("RGB")
    im.save(out_png, optimize=True)
    import os; os.remove(tmp)
