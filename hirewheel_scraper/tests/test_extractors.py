"""Selector-lock tests for every page extractor.

Each fixture mirrors the real class names/attributes observed on the live pages
(2026-07-20). If Hirewheel changes its markup, the matching test fails loudly so
we know exactly which extractor to update.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hwscraper.extractors import get_extractor, parse_html  # noqa: E402


def _run(page_key: str, html: str):
    return get_extractor(page_key)(parse_html(html))


def test_internship_prep():
    html = """
    <article class="elite102-card">
      <span class="elite102-card__status">Not Started</span>
      <div class="elite102-card__category">JavaScript (React)</div>
      <h3 class="elite102-card__title">Dinner and a Movie App</h3>
      <p class="elite102-card__description">Make a matching website...</p>
      <div class="elite102-card__tags"><span class="elite102-card__tag">JavaScript</span>
        <span class="elite102-card__tag">React</span><span class="elite102-card__tag">25 XP</span></div>
      <a class="elite102-card__btn" href="/internship-prep/js-dinner-and-a-movie">View</a>
    </article>"""
    items = _run("internship_prep", html)
    assert len(items) == 1
    it = items[0]
    assert it.uid == "prep_project:/internship-prep/js-dinner-and-a-movie"
    assert it.fields["status"] == "Not Started"
    assert it.fields["tags"] == ["JavaScript", "React", "25 XP"]


def test_marketplace():
    html = """
    <a class="pj-card" href="/marketplace/projects/acme-dashboard">
      <span class="pill">OPEN</span>
      <h3 class="pj-title">Acme Sales Dashboard</h3>
      <div class="goal">Build a dashboard...</div>
      <div class="platforms">Looker Studio CSV</div>
      <div class="meta-row"><span class="xp">100 XP</span></div>
    </a>"""
    items = _run("marketplace", html)
    assert len(items) == 1
    assert items[0].uid == "marketplace:/marketplace/projects/acme-dashboard"
    assert items[0].fields["xp"] == "100 XP"
    assert items[0].fields["pills"] == ["OPEN"]


def test_college_pathways():
    html = """
    <div class="cp-partner-grid">
      <a class="cp-partner-card" href="#">
        <h3 class="cp-partner-name">Austin Community College</h3>
        <p class="cp-partner-tagline">Transfer pathway</p>
        <div class="cp-partner-tags"><span class="cp-partner-tag">Austin, TX</span>
          <span class="cp-partner-tag">Free Tuition pilot</span></div>
        <span class="cp-partner-cta">Learn more</span>
      </a></div>"""
    items = _run("college_pathways", html)
    assert len(items) == 1
    assert items[0].title == "Austin Community College"
    assert items[0].fields["tags"] == ["Austin, TX", "Free Tuition pilot"]


def test_learning_modules():
    html = """
    <section class="learning-module" data-status="completed">
      <h4 class="learning-module__title">October 2025 Coding Practice</h4>
      <p class="learning-module__progress">4 / 4 activities complete</p>
      <p class="learning-module__description">Monthly set.</p>
      <ul>
        <li class="learning-activity" data-status="completed">
          <div class="learning-activity__title">Problem 1</div>
          <span class="learning-activity__xp">10 XP</span></li>
        <li class="learning-activity" data-status="not-started">
          <div class="learning-activity__title">Problem 2</div>
          <span class="learning-activity__xp">10 XP</span></li>
      </ul></section>"""
    items = _run("modules", html)
    kinds = [i.kind for i in items]
    assert kinds == ["learning_module", "learning_activity", "learning_activity"]
    # progress/status excluded → module fields carry no user-progress noise
    mod = items[0]
    assert "progress" not in mod.fields and "status" not in mod.fields
    assert items[1].uid == "learning_activity:october-2025-coding-practice:problem-1"


def test_surveys_sections():
    html = """
    <main>
      <h5 class="text-uppercase">Available now</h5>
      <div class="card"><div class="card-body">
        <div class="fw-semibold">New Program Feedback</div>
        <div class="text-muted">Due Jul 25</div></div></div>
      <h5 class="text-uppercase">Completed</h5>
      <div class="card"><div class="card-body">
        <div class="fw-semibold">Dietary Restrictions</div>
        <div class="text-muted">Submitted Jun 07, 2026</div></div></div>
    </main>"""
    items = _run("surveys", html)
    assert len(items) == 2
    avail = next(i for i in items if i.title == "New Program Feedback")
    assert avail.fields["section"] == "Available now"


def test_news():
    html = """
    <a class="news-sidebar-item" href="/news/136">
      <div class="news-sidebar-item-date">Jun 12, 2026</div>
      <div class="news-sidebar-item-title">STAR Response Raffle Round 2</div></a>"""
    items = _run("news", html)
    assert items[0].uid == "news:/news/136"
    assert items[0].fields["date"] == "Jun 12, 2026"


def test_program_deliverables():
    html = """
    <a href="#deliverable-resume" class="d-flex">
      <div class="fw-semibold">C2C-Approved Resume</div>
      <div class="text-muted">C2C-Approved Resume Approved · due Jun 5</div>
      <span class="badge">Done</span></a>"""
    items = _run("program", html)
    assert items[0].uid == "deliverable:deliverable-resume"
    assert items[0].fields["status"] == "Done"
    assert items[0].fields["detail"] == "Approved · due Jun 5"


def test_special_events_current_vs_past():
    html = """
    <div id="current-events"><section class="mb-4">
      <h3 class="fw-bold">Upcoming Hackathon</h3>
      <p class="text-muted">Aug 1, 2026</p></section></div>
    <div id="past-events"><section class="mb-4">
      <h3 class="fw-bold">National AI Literacy Day</h3>
      <p class="text-muted">Apr 2026</p></section></div>"""
    items = _run("special_events", html)
    cur = next(i for i in items if i.title == "Upcoming Hackathon")
    assert cur.fields["status"] == "current"
    assert cur.uid == "event:current:upcoming-hackathon"


def test_my_projects_empty():
    html = '<main><h1 class="fw-bold">My Assigned Projects</h1>' \
           '<div class="alert alert-info"><p class="mb-0">You currently have no assigned projects.</p></div></main>'
    assert _run("my_projects", html) == []


def test_my_projects_populated():
    html = '<main><div class="card"><div class="card-body">' \
           '<h5 class="fw-semibold">Acme Internship</h5><span class="badge">Active</span>' \
           '<a href="/intern/projects/9">Open</a></div></div></main>'
    items = _run("my_projects", html)
    assert len(items) == 1 and items[0].kind == "assigned_project"
    assert items[0].fields["status"] == "Active"


def test_meetings_empty():
    html = '<main><div class="meetings-container"><div class="meeting-card">' \
           'No interviews scheduled yet. When an employer schedules an interview it will appear here.' \
           '</div></div></main>'
    assert _run("meetings", html) == []


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\n{len(fns)} tests passed.")


if __name__ == "__main__":
    _run_all()
