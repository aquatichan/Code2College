"""GitHub data fetching for Portfolix.

Uses only the public REST API — no token required. Profile, repos, and language
breakdown come straight from the public endpoints. "Featured Projects" are the
top repos by stars (the public API can't read GitHub's pinned selection). A token
is optional: if present it only raises the rate limit, nothing more.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

import requests

REST_API = "https://api.github.com"


@dataclass
class Repo:
    name: str
    description: str
    url: str
    homepage: str
    language: str
    stars: int
    forks: int
    topics: list[str] = field(default_factory=list)
    pinned: bool = False
    updated_at: str = ""
    created_at: str = ""
    pushed_at: str = ""

    # Optional AI-generated paragraph (filled in later by the enhancer).
    ai_summary: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "url": self.url,
            "homepage": self.homepage,
            "language": self.language,
            "stars": self.stars,
            "forks": self.forks,
            "topics": self.topics,
            "pinned": self.pinned,
            "updated_at": self.updated_at,
            "created_at": self.created_at,
            "pushed_at": self.pushed_at,
            "ai_summary": self.ai_summary,
        }


@dataclass
class Profile:
    login: str
    name: str
    bio: str
    avatar_url: str
    html_url: str
    company: str
    location: str
    blog: str
    followers: int
    following: int
    public_repos: int

    def to_dict(self) -> dict:
        return {
            "login": self.login,
            "name": self.name,
            "bio": self.bio,
            "avatar_url": self.avatar_url,
            "html_url": self.html_url,
            "company": self.company,
            "location": self.location,
            "blog": self.blog,
            "followers": self.followers,
            "following": self.following,
            "public_repos": self.public_repos,
        }


@dataclass
class PortfolioData:
    profile: Profile
    repos: list[Repo]
    pinned: list[Repo]
    languages: list[tuple[str, float]] # language + percentage
    total_stars: int
    total_forks: int
    contributions: int | None = None  # last-year contribution count, if available

    # Derived chart metrics (computed in build()).
    repos_by_year: dict[str, int] = field(default_factory=dict)  # creation-year histogram
    activity_by_year: dict[str, int] = field(default_factory=dict)  # last-push-year histogram
    top_topics: list[tuple[str, int]] = field(default_factory=list)  # (topic, count)
    top_starred: list[tuple[str, int]] = field(default_factory=list)  # (repo, stars)

    # Optional AI-generated narrative fields (filled by the enhancer).
    ai_narrative: str = ""      # a short "about / ambitions" paragraph
    ai_headline: str = ""       # a punchy one-line headline
    cover_letter: str = ""      # AI-drafted cover letter body
    brag_sheet: list[str] = field(default_factory=list)  # quantified achievement bullets
    beautified_css: dict = field(default_factory=dict)  # {doc_id: ai-beautified css} for the Studio

    def to_dict(self) -> dict:
        return {
            "profile": self.profile.to_dict(),
            "repos": [r.to_dict() for r in self.repos],
            "pinned": [r.to_dict() for r in self.pinned],
            "languages": [{"name": n, "pct": p} for n, p in self.languages],
            "total_stars": self.total_stars,
            "total_forks": self.total_forks,
            "contributions": self.contributions,
            "repos_by_year": self.repos_by_year,
            "activity_by_year": self.activity_by_year,
            "top_topics": [{"topic": t, "count": c} for t, c in self.top_topics],
            "top_starred": [{"name": n, "stars": s} for n, s in self.top_starred],
            "ai": {
                "narrative": self.ai_narrative,
                "headline": self.ai_headline,
                "cover_letter": self.cover_letter,
                "brag_sheet": self.brag_sheet,
                "beautified_css": self.beautified_css,
            },
        }


class GitHubError(Exception):
    """Raised when GitHub returns an error we cannot recover from."""


class GitHubClient:
    def __init__(self, username: str, token: str | None = None):
        if not username:
            raise GitHubError("A GitHub username is required.")
        self.username = username
        self.token = token
        self.session = requests.Session()
        headers = {"Accept": "application/vnd.github+json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self.session.headers.update(headers)

    # ---- REST helpers -----------------------------------------------------

    def _rest(self, path: str, **params) -> object:
        resp = self.session.get(f"{REST_API}{path}", params=params, timeout=30)
        if resp.status_code == 404:
            raise GitHubError(f"Not found: {path} (is the username correct?)")
        if resp.status_code == 403 and "rate limit" in resp.text.lower():
            raise GitHubError(
                "GitHub API rate limit hit (60 requests/hr without a token). "
                "Wait an hour, or optionally set GITHUB_TOKEN in .env for a higher limit."
            )
        if not resp.ok:
            raise GitHubError(f"GitHub REST error {resp.status_code}: {resp.text[:200]}")
        return resp.json()

    def fetch_profile(self) -> Profile:
        d = self._rest(f"/users/{self.username}")
        return Profile(
            login=d["login"],
            name=d.get("name") or d["login"],
            bio=d.get("bio") or "",
            avatar_url=d.get("avatar_url") or "",
            html_url=d.get("html_url") or "",
            company=d.get("company") or "",
            location=d.get("location") or "",
            blog=d.get("blog") or "",
            followers=d.get("followers", 0),
            following=d.get("following", 0),
            public_repos=d.get("public_repos", 0),
        )

    def fetch_repos(self) -> list[Repo]:
        """All public, non-fork repos, paginated."""
        repos: list[Repo] = []
        page = 1
        while True:
            batch = self._rest(
                f"/users/{self.username}/repos",
                per_page=100,
                page=page,
                sort="updated",
                type="owner",
            )
            if not batch:
                break
            for d in batch:
                if d.get("fork"):
                    continue
                repos.append(
                    Repo(
                        name=d["name"],
                        description=d.get("description") or "",
                        url=d["html_url"],
                        homepage=(d.get("homepage") or "").strip(),
                        language=d.get("language") or "",
                        stars=d.get("stargazers_count", 0),
                        forks=d.get("forks_count", 0),
                        topics=d.get("topics", []),
                        updated_at=d.get("updated_at", ""),
                        created_at=d.get("created_at", ""),
                        pushed_at=d.get("pushed_at", ""),
                    )
                )
            if len(batch) < 100:
                break
            page += 1
        return repos

    def fetch_language_breakdown(self, repos: list[Repo]) -> list[tuple[str, float]]:
        """Aggregate byte counts across repos into a percentage breakdown.

        Uses the per-repo /languages endpoint so multi-language repos are counted
        fairly (not just the single "primary" language).
        """
        totals: dict[str, int] = defaultdict(int)
        for repo in repos:
            try:
                data = self._rest(f"/repos/{self.username}/{repo.name}/languages")
            except GitHubError:
                continue
            for lang, byte_count in data.items():
                totals[lang] += byte_count

        grand_total = sum(totals.values())
        if grand_total == 0:
            return []
        breakdown = [
            (lang, round(count / grand_total * 100, 1))
            for lang, count in totals.items()
        ]
        breakdown.sort(key=lambda x: x[1], reverse=True)
        return breakdown

    # ---- Orchestration ----------------------------------------------------

    def build(self, featured_n: int = 6) -> PortfolioData:
        """Fetch everything using only the public REST API (no token required).

        "Featured Projects" are the top repos by stars, then recency — the public
        API can't read GitHub's pinned-repo selection (that needs an authed
        GraphQL call), and top-starred is a good tokenless substitute.
        """
        print(f"Fetching profile for @{self.username}…")
        profile = self.fetch_profile()

        print("Fetching repositories…")
        repos = self.fetch_repos()

        print("Fetching language breakdown…")
        languages = self.fetch_language_breakdown(repos)

        # Feature top repos by stars, then most recently updated.
        featured = sorted(
            repos,
            key=lambda r: (r.stars, r.updated_at),
            reverse=True,
        )[:featured_n]
        for repo in featured:
            repo.pinned = True

        return PortfolioData(
            profile=profile,
            repos=repos,
            pinned=featured,
            languages=languages,
            total_stars=sum(r.stars for r in repos),
            total_forks=sum(r.forks for r in repos),
            contributions=None,  # not available via the public REST API
            repos_by_year=self._year_histogram(repos, "created_at"),
            activity_by_year=self._year_histogram(repos, "pushed_at"),
            top_topics=self._topic_frequency(repos),
            top_starred=self._top_starred(repos),
        )

    # ---- Derived metrics for charts ---------------------------------------

    @staticmethod
    def _year_histogram(repos: list[Repo], attr: str) -> dict[str, int]:
        """Count repos by the year of an ISO timestamp attribute, gap-filled.

        Returns an ordered {year: count} dict spanning min→max year so the
        chart has no missing columns.
        """
        years: list[int] = []
        for r in repos:
            ts = getattr(r, attr, "")
            if ts and len(ts) >= 4 and ts[:4].isdigit():
                years.append(int(ts[:4]))
        if not years:
            return {}
        counts: dict[int, int] = defaultdict(int)
        for y in years:
            counts[y] += 1
        return {str(y): counts.get(y, 0) for y in range(min(years), max(years) + 1)}

    @staticmethod
    def _topic_frequency(repos: list[Repo], limit: int = 10) -> list[tuple[str, int]]:
        counts: dict[str, int] = defaultdict(int)
        for r in repos:
            for t in r.topics:
                counts[t] += 1
        ranked = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
        return ranked[:limit]

    @staticmethod
    def _top_starred(repos: list[Repo], limit: int = 8) -> list[tuple[str, int]]:
        ranked = sorted(
            (r for r in repos if r.stars > 0),
            key=lambda r: r.stars,
            reverse=True,
        )
        return [(r.name, r.stars) for r in ranked[:limit]]
