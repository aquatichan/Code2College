"""Pure scraping core, copied verbatim from hirewheel_scraper_web.

`models`, `diff` and every module under `extractors/` are byte-identical to the
desktop project: they are pure functions over HTML and dataclasses, with no
dependency on Playwright, storage, or any UI. Keep them that way — if a change
is needed here, it should also land in the web version.
"""
