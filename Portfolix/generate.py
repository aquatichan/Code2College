#!/usr/bin/env python3
"""Portfolix — GitHub Portfolio Auto-Exporter.

Fetches your public GitHub data and regenerates a responsive portfolio website
and/or a technical CV with a single command.

Examples:
    python generate.py --username octocat
    python generate.py --username octocat --html
    python generate.py --username octocat --output dist
    python generate.py                       # uses GITHUB_USERNAME from .env
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from portfolix.ai_enhancer import AIEnhancer
from portfolix.builder import Builder
from portfolix.github_client import GitHubClient, GitHubError


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="portfolix",
        description="Auto-export a GitHub portfolio site, technical CV, cover letter, or brag sheet.",
    )
    p.add_argument(
        "--username", "-u",
        help="GitHub username (falls back to GITHUB_USERNAME in .env).",
    )
    p.add_argument("--html", action="store_true", help="Generate the HTML portfolio site.")
    p.add_argument(
        "--data-only", action="store_true",
        help="Only fetch data and write data.json (for the static landing site). Default when no other flag is given.",
    )
    p.add_argument(
        "--output", "-o", default="output",
        help="Output directory (default: ./output).",
    )
    p.add_argument(
        "--no-ai", action="store_true",
        help="Skip Gemini enhancement even if GEMINI_API_KEY is set.",
    )
    p.add_argument(
        "--beautify", action="store_true",
        help="Use Gemini to analyze & beautify the CSS of the HTML exports (needs GEMINI_API_KEY).",
    )
    return p.parse_args(argv)


def _ai_is_empty(ai: dict) -> bool:
    return not any((
        ai.get("narrative"), ai.get("headline"), ai.get("cover_letter"),
        ai.get("brag_sheet"), ai.get("beautified_css"),
    ))


def _preserve_ai(payload: dict, data_path, username: str) -> dict:
    """If the fresh payload has no AI copy but an existing data.json for the same
    user does, carry the old AI copy (and per-repo ai_summary) forward."""
    new_ai = payload.get("ai", {})
    if not _ai_is_empty(new_ai):
        return payload  # this run produced AI; nothing to preserve
    if not data_path.exists():
        return payload
    try:
        old = json.loads(data_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return payload
    if old.get("profile", {}).get("login") != username:
        return payload  # different user's file; don't mix
    if _ai_is_empty(old.get("ai", {})):
        return payload  # old file had no AI either
    payload["ai"] = old["ai"]
    # Restore per-repo AI summaries by name.
    old_sum = {r["name"]: r.get("ai_summary", "") for r in old.get("repos", [])}
    for coll in ("repos", "pinned"):
        for r in payload.get(coll, []):
            if not r.get("ai_summary") and old_sum.get(r["name"]):
                r["ai_summary"] = old_sum[r["name"]]
    print("[note] Gemini produced no AI this run — kept the AI copy from the "
          "previous data.json so the site stays enhanced.", file=sys.stderr)
    return payload


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = parse_args(argv)

    # Default (no flags): build data.json for the static landing site.
    # data.json is always written — the HTML exports and the landing site all
    # consume it — with --html as an optional standalone static export.
    any_flag = args.html or args.data_only
    want_html = args.html

    username = args.username or os.getenv("GITHUB_USERNAME")
    if not username:
        print(
            "Error: no GitHub username. Pass --username USER or set "
            "GITHUB_USERNAME in .env (copy .env.example to .env).",
            file=sys.stderr,
        )
        return 2

    # Token is optional and only raises the rate limit; the app is tokenless.
    token = os.getenv("GITHUB_TOKEN") or None
    gemini_key = None if args.no_ai else (os.getenv("GEMINI_API_KEY") or None)

    print(f"PORTFOLIX → building portfolio for @{username}\n")

    try:
        client = GitHubClient(username=username, token=token)
        data = client.build()
    except GitHubError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    enhancer = AIEnhancer(gemini_key)
    enhancer.enhance(data)

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    beautifier = enhancer.beautify_css if args.beautify else None
    if args.beautify and not enhancer.enabled:
        print("[note] --beautify requested but Gemini is unavailable; using template CSS.",
              file=sys.stderr)
    builder = Builder(data, beautifier=beautifier)
    produced: list[Path] = []

    # Always write data.json — it powers the static landing site.
    data_path = out_dir / "data.json"
    payload = data.to_dict()

    # If this run produced no AI (e.g. Gemini quota exhausted), don't wipe AI copy
    # that a previous successful run already saved for the same user — carry it
    # forward so the site keeps showing enhancements instead of reverting to bare.
    payload = _preserve_ai(payload, data_path, username)

    data_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    produced.append(data_path)
    print(f"✓ DATA → {data_path}")

    if want_html:
        path = builder.render_html(out_dir / f"{username}.html")
        produced.append(path)
        print(f"✓ HTML → {path}")

    print(f"\nDone: {len(produced)} file(s) written to {out_dir}/.")
    if not any_flag:
        print("Tip: open the landing site (site/index.html) to pick & customize documents.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
