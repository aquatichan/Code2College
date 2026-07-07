"""Optional Gemini-powered polish for portfolio copy.

Everything here is best-effort: if no API key is set, the library is missing, or
a call fails, we return the original text unchanged. The portfolio must always
generate without Gemini.
"""

from __future__ import annotations

import json
import sys
import time

from .github_client import PortfolioData, Repo

MODEL = "gemini-2.5-flash-lite"

# Transient "server busy" errors worth a short retry (recover in seconds).
_RETRYABLE = ("503", "unavailable", "overloaded", "500", "internal")
# Signals a DAILY quota wall — retrying is hopeless and wastes more of the quota.
_DAILY_QUOTA = ("perday", "per_day", "requestsperdayper", "free_tier_requests")


class QuotaExhausted(Exception):
    """Raised internally when the daily free-tier quota is spent."""


class AIEnhancer:
    def __init__(self, api_key: str | None):
        self.enabled = False
        self._model = None
        self._quota_hit = False  # latch: once the daily quota is gone, stop calling
        if not api_key:
            return
        try:
            import google.generativeai as genai

            genai.configure(api_key=api_key)
            self._model = genai.GenerativeModel(MODEL)
            self.enabled = True
        except Exception as exc:  # ImportError or config error
            print(f"[warn] Gemini unavailable ({exc}); skipping AI polish.", file=sys.stderr)

    def _generate(self, prompt: str, retries: int = 1) -> str | None:
        if not self._model or self._quota_hit:
            return None
        delay = 8
        for attempt in range(retries + 1):
            try:
                resp = self._model.generate_content(prompt)
                return (resp.text or "").strip()
            except Exception as exc:
                msg = str(exc).lower()
                # Daily quota gone: don't retry, and stop all further calls this run.
                if ("429" in msg or "quota" in msg or "exhausted" in msg) and \
                        any(t in msg.replace(" ", "") for t in _DAILY_QUOTA):
                    self._quota_hit = True
                    print("[warn] Gemini DAILY free-tier quota is exhausted — skipping "
                          "the rest of the AI steps. It resets at midnight Pacific.",
                          file=sys.stderr)
                    return None
                # A generic 429 (per-minute) or a busy server: one short retry.
                if attempt < retries and ("429" in msg or any(t in msg for t in _RETRYABLE)):
                    print(f"[warn] Gemini busy/throttled; one retry in {delay}s…", file=sys.stderr)
                    time.sleep(delay)
                    continue
                print(f"[warn] Gemini call failed ({str(exc)[:120]}).", file=sys.stderr)
                return None
        return None

    def enhance(self, data: PortfolioData) -> None:
        """Mutate `data` in place with all AI-generated copy.

        Populates polished bio, per-repo summaries, an about/ambitions narrative,
        a headline, a cover letter, and a quantified brag sheet. Each step is
        best-effort and independently degrades if a call fails.
        """
        if not self.enabled:
            return

        print("Enhancing copy with Gemini (bio, summaries, narrative, cover letter, brag sheet, style)…")
        self._polish_bio(data)
        self._summarize_repos(data.pinned)
        self._write_narrative(data)
        self._write_style_pack(data)
        self._write_cover_letter(data)
        self._write_brag_sheet(data)

        # Never fail silently: if Gemini was enabled but nothing came back, the
        # Studio would show "AI unavailable" with no clue why. Say so loudly.
        if not any((data.ai_narrative, data.ai_headline, data.cover_letter,
                    data.brag_sheet, data.beautified_css)):
            print(
                "[warn] Gemini was enabled but produced NO content — likely a "
                "rate limit or quota issue. Wait a minute and re-run generate.py; "
                "the site will show 'AI unavailable' until data.json has AI copy.",
                file=sys.stderr,
            )

    # A reusable rule block that steers every copy prompt toward human, specific,
    # hireable writing and away from the tells that make text read as AI-generated.
    _VOICE = (
        "Write like a sharp human, not an AI. Hard rules:\n"
        "- BAN these words/phrases entirely: passionate, leverage, cutting-edge, "
        "seamless, robust, dynamic, innovative, dedicated, driven, detail-oriented, "
        "results-driven, team player, synergy, utilize, spearheaded, plethora, "
        "tapestry, realm, testament, delve, in today's world, fast-paced.\n"
        "- Prefer concrete nouns and strong plain verbs (built, shipped, cut, "
        "designed, automated, scaled) over adjectives.\n"
        "- Use specifics from the real data (project names, the actual problem "
        "solved, the tech, any numbers). Never invent facts, employers, or metrics "
        "that aren't given.\n"
        "- Vary sentence length. No filler. Every clause earns its place."
    )

    def _polish_bio(self, data: PortfolioData) -> None:
        p = data.profile
        top_langs = ", ".join(lang for lang, _ in data.languages[:5]) or "various technologies"
        prompt = (
            "Rewrite this developer bio as ONE natural sentence (15-25 words) for the "
            "top of a portfolio. Say what they actually build and with what — no "
            "adjective soup. Return ONLY the sentence, no quotes, no preamble.\n\n"
            f"{self._VOICE}\n\n"
            f"Name: {p.name}\n"
            f"Current bio: {p.bio or '(none)'}\n"
            f"Top languages: {top_langs}\n"
            f"Public repos: {p.public_repos}\n"
        )
        result = self._generate(prompt)
        if result:
            data.profile.bio = result.strip().strip('"')

    def _summarize_repos(self, repos: list[Repo]) -> None:
        """Batch a single request for punchy one-liners across featured repos."""
        if not repos:
            return
        items = [
            {"name": r.name, "description": r.description, "language": r.language}
            for r in repos
        ]
        prompt = (
            "For each project, write a resume-ready line (15-25 words) that leads with "
            "what it DOES for a user or what problem it solves, then names the notable "
            "technical part. Start with a strong verb or the concrete thing it is. "
            "Don't just restate the repo name. Return ONLY a JSON object mapping each "
            "project name to its summary string. No markdown fences.\n\n"
            f"{self._VOICE}\n\n"
            f"{json.dumps(items, indent=2)}"
        )
        raw = self._generate(prompt)
        if not raw:
            return
        # Strip accidental markdown fences.
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json").strip()
        try:
            summaries = json.loads(raw)
        except json.JSONDecodeError:
            print("[warn] Gemini returned unparseable JSON; skipping summaries.", file=sys.stderr)
            return
        for repo in repos:
            summary = summaries.get(repo.name)
            if isinstance(summary, str) and summary.strip():
                repo.ai_summary = summary.strip()

    def _project_digest(self, data: PortfolioData, n: int = 6) -> str:
        """A compact text digest of featured projects for narrative prompts."""
        lines = []
        for r in data.pinned[:n]:
            desc = r.ai_summary or r.description or "(no description)"
            lines.append(f"- {r.name} ({r.language or 'n/a'}, ★{r.stars}): {desc}")
        return "\n".join(lines)

    def _write_narrative(self, data: PortfolioData) -> None:
        p = data.profile
        top_langs = ", ".join(lang for lang, _ in data.languages[:6]) or "various technologies"
        prompt = (
            "Write the 'About' section for a developer's portfolio, grounded in their "
            "REAL projects below. Return ONLY a JSON object with two keys:\n"
            '  "headline": a specific, confident tagline (10-15 words) that names what '
            "they do — not a generic slogan (bad: 'Building the future'; good: "
            "'Deploying full-stack web apps, from civic tools to the future of fintech'),\n"
            '  "narrative": 2-3 first-person sentences (65-90 words) about what they '
            "build, the range shown across their projects, and where they're heading. "
            "Reference at least one real project by name. Sound like a real person "
            "talking, not a LinkedIn bot.\n"
            "No markdown fences.\n\n"
            f"{self._VOICE}\n\n"
            f"Name: {p.name}\n"
            f"Bio: {p.bio or '(none)'}\n"
            f"Top languages: {top_langs}\n"
            f"Public repos: {p.public_repos}, total stars: {data.total_stars}\n"
            f"Featured projects:\n{self._project_digest(data)}\n"
        )
        obj = self._generate_json(prompt)
        if isinstance(obj, dict):
            if isinstance(obj.get("headline"), str):
                data.ai_headline = obj["headline"].strip().strip('"')
            if isinstance(obj.get("narrative"), str):
                data.ai_narrative = obj["narrative"].strip()

    def _write_style_pack(self, data: PortfolioData) -> None:
        """Ask Gemini for a visual-identity "style pack" the Studio's Beautify
        toggle applies: gradient headings, distinctive heading typography, accent
        colors, radii. Declarative fields only (the Studio turns them into a safe
        CSS overlay), so a wild answer still can't break document layout.
        """
        p = data.profile
        top_langs = ", ".join(lang for lang, _ in data.languages[:5]) or "general software"
        prompt = (
            "You are an award-winning brand + web designer. Design a STUNNING, "
            f"professional visual identity for {p.name}'s portfolio (works in "
            f"{top_langs}). Think modern tech portfolios and premium résumés — "
            "confident color, real typographic pairing, tasteful depth. Not default, "
            "not gaudy.\n\n"
            "Choose fonts ONLY from this Google Fonts list (the app loads these):\n"
            "  Heading sans: Poppins, Montserrat, Sora, Space Grotesk, Outfit, Archivo\n"
            "  Serif: Playfair Display, Fraunces, Cormorant Garamond, Lora\n"
            "  Script (signatures/flourish): Dancing Script, Great Vibes, Sacramento\n"
            "  Body: Inter, Work Sans, DM Sans, Nunito Sans\n\n"
            "Return ONLY a JSON object (no markdown fences) with these keys:\n"
            '  "name": short style name (e.g. "Cobalt Studio"),\n'
            '  "heading_family": one heading font NAME from the list above,\n'
            '  "body_family": one body font NAME from the list above,\n'
            '  "signature_family": one script font NAME (used for the cover-letter signature),\n'
            '  "accent_light": hex accent for light surfaces (readable on white),\n'
            '  "accent_dark": hex accent for dark surfaces (readable on near-black),\n'
            '  "gradient": {"from": hex, "to": hex, "angle": "135deg"} — harmonious hues '
            "that read on BOTH light and dark; used for headings and accents,\n"
            '  "heading_weight": 600-800,\n'
            '  "letter_spacing": heading tracking like "-0.02em",\n'
            '  "radius": card radius like "16px",\n'
            '  "vibe": one of "warm", "cool", "mono", "vibrant" — the overall mood.\n'
            "Ensure strong contrast and accessibility. Pick a pairing that feels "
            "intentional (e.g. a geometric sans heading + a clean sans body, or a "
            "serif display + sans body)."
        )
        obj = self._generate_json(prompt)
        if not isinstance(obj, dict):
            return
        allowed = {
            "name", "heading_family", "body_family", "signature_family",
            "accent_light", "accent_dark", "gradient", "heading_weight",
            "letter_spacing", "radius", "vibe",
        }
        pack = {k: obj[k] for k in allowed if k in obj and obj[k] not in (None, "")}
        g = pack.get("gradient")
        if g is not None and not (isinstance(g, dict) and g.get("from") and g.get("to")):
            pack.pop("gradient", None)
        if pack:
            data.beautified_css = pack

    def _write_cover_letter(self, data: PortfolioData) -> None:
        p = data.profile
        top_langs = ", ".join(lang for lang, _ in data.languages[:6]) or "various technologies"
        prompt = (
            "Write the BODY of a software-engineering cover letter that a hiring "
            "manager would actually finish reading. Structure:\n"
            "  P1 (hook): open with a specific, genuine reason for interest — tie one "
            "of their real projects to what [Company] does. No 'I am writing to apply'.\n"
            "  P2 (proof): tell a mini-story about ONE real project below — the problem, "
            "what they built, the tech, the outcome. Concrete, not a skills list.\n"
            "  P3 (fit + close): connect their range to the [Role] and end with a "
            "confident, low-key call to action.\n"
            "~250-330 words, first person, warm but professional. Use placeholders "
            "[Company], [Role], and [specific detail about the company] where a real "
            "applicant would personalize. Return ONLY the body text — no 'Dear …' line, "
            "no 'Sincerely', no signature.\n\n"
            f"{self._VOICE}\n\n"
            f"Name: {p.name}\n"
            f"Bio: {p.bio or '(none)'}\n"
            f"Top languages: {top_langs}\n"
            f"Featured projects:\n{self._project_digest(data)}\n"
        )
        result = self._generate(prompt)
        if result:
            data.cover_letter = result.strip()

    def _write_brag_sheet(self, data: PortfolioData) -> None:
        prompt = (
            "Write 6-8 resume achievement bullets from this developer's real GitHub "
            "work. Each bullet: start with a strong past-tense verb, name the real "
            "project and tech, and state the outcome or scope. Use a number ONLY when "
            "it's supported by the data given (repo count, stars, languages) — do NOT "
            "fabricate metrics like user counts or performance gains. It's fine for a "
            "bullet to be qualitative if there's no real number. "
            "Return ONLY a JSON array of strings. No markdown fences.\n\n"
            f"{self._VOICE}\n\n"
            f"Public repos: {data.profile.public_repos}\n"
            f"Total stars: {data.total_stars}, total forks: {data.total_forks}\n"
            f"Contributions/yr: {data.contributions if data.contributions is not None else 'n/a'}\n"
            f"Top languages: {', '.join(l for l, _ in data.languages[:6])}\n"
            f"Top topics: {', '.join(t for t, _ in data.top_topics[:8])}\n"
            f"Featured projects:\n{self._project_digest(data, n=8)}\n"
        )
        arr = self._generate_json(prompt)
        if isinstance(arr, list):
            data.brag_sheet = [str(b).strip() for b in arr if str(b).strip()]

    def beautify_css(self, current_css: str, doc_kind: str = "portfolio") -> str | None:
        """Analyze and beautify a document's CSS, returning improved CSS only.

        Used by the CLI's `--beautify` step. Returns None if AI is unavailable
        or the response is empty, so callers keep the original stylesheet.
        """
        if not self.enabled:
            return None
        prompt = (
            f"You are a senior front-end designer. Improve the CSS below for a "
            f"'{doc_kind}' document. Refine spacing, typography scale, color harmony, "
            "and visual hierarchy. Keep it theme-aware (light/dark via prefers-color-scheme "
            "and [data-theme]) and keep all existing selectors/class names so the HTML "
            "still matches. Do not add external resources. Return ONLY the full CSS, "
            "no explanation, no markdown fences.\n\n"
            f"{current_css}"
        )
        result = self._generate(prompt)
        if not result:
            return None
        result = result.strip()
        if result.startswith("```"):
            # Strip a ```css … ``` fence if the model added one.
            parts = result.split("```")
            result = parts[1] if len(parts) > 1 else result
            result = result.lstrip("css").strip()
        return result or None

    # ---- JSON helper ------------------------------------------------------

    def _generate_json(self, prompt: str):
        """Generate and parse a JSON response, tolerating markdown fences."""
        raw = self._generate(prompt)
        if not raw:
            return None
        raw = raw.strip()
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            raw = raw.lstrip("json").strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            print("[warn] Gemini returned unparseable JSON; skipping.", file=sys.stderr)
            return None
