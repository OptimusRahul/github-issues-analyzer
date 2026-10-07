"""Weekly digest: new and growing themes, issues needing attention, likely duplicates still open."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from triage.config import Config
from triage.dupes import find_candidates
from triage.llm import ChatModel
from triage.store import Store
from triage.sync import ISO_FORMAT, iso
from triage.text import sanitize
from triage.themes import cluster, name_theme

MAINTAINERS = ("OWNER", "MEMBER", "COLLABORATOR")
SECTION_LIMIT = 10
THEME_LIMIT = 5


@dataclass
class Theme:
    name: str
    numbers: list[int]
    new: int  # opened in this window
    previous: int  # opened in the window before


@dataclass
class Digest:
    window_days: int
    new_themes: list[Theme] = field(default_factory=list)
    growing_themes: list[Theme] = field(default_factory=list)
    most_wanted: list[dict] = field(default_factory=list)
    waiting: list[tuple[dict, int]] = field(default_factory=list)  # (issue, days since the last comment)
    open_duplicates: list[tuple[int, int, float]] = field(default_factory=list)  # (newer, older, similarity)


def split_themes(themes: list[Theme]) -> tuple[list[Theme], list[Theme]]:
    """New: most of the theme was opened this window. Growing: more opened this window than the one before."""
    new = sorted((t for t in themes if t.new * 2 > len(t.numbers)), key=lambda t: -len(t.numbers))
    growing = sorted(
        (t for t in themes if t not in new and t.new > t.previous and t.new >= 2), key=lambda t: t.previous - t.new
    )
    return new[:THEME_LIMIT], growing[:THEME_LIMIT]


def _days_since(timestamp: str, now: datetime) -> int:
    return (now - datetime.strptime(timestamp, ISO_FORMAT).replace(tzinfo=timezone.utc)).days


def build_digest(store: Store, model: str, cfg: Config, now: datetime, namer: ChatModel | None = None) -> Digest:
    d = cfg.digest
    digest = Digest(window_days=d.window_days)
    open_issues = {i["number"]: i for i in store.issues() if i["state"] == "open"}
    window_start = iso(now - timedelta(days=d.window_days))
    previous_start = iso(now - timedelta(days=2 * d.window_days))

    numbers, vectors = store.matrix(model)
    rows = [j for j, n in enumerate(numbers) if int(n) in open_issues]
    open_numbers = [int(numbers[j]) for j in rows]
    themes = []
    for group in cluster(vectors[rows], d.theme_threshold, d.min_theme_size):
        members = [open_numbers[j] for j in group]
        created = [open_issues[n]["created_at"] for n in members]
        new = sum(c >= window_start for c in created)
        previous = sum(previous_start <= c < window_start for c in created)
        themes.append(Theme("", members, new, previous))
    digest.new_themes, digest.growing_themes = split_themes(themes)
    corpus = [open_issues[n]["title"] for n in open_numbers]
    for theme in digest.new_themes + digest.growing_themes:  # name only the themes shown
        theme.name = name_theme([open_issues[n]["title"] for n in theme.numbers], corpus, namer)

    replied = store.maintainer_replied(MAINTAINERS)
    wanted = [i for n, i in open_issues.items() if i["reactions_total"] > 0 and n not in replied]
    digest.most_wanted = sorted(wanted, key=lambda i: (-i["reactions_total"], i["number"]))[:SECTION_LIMIT]

    waiting = []
    for number, (association, created_at) in store.latest_comments().items():
        if number in open_issues and association not in MAINTAINERS:
            days = _days_since(created_at, now)
            if days >= d.waiting_days:
                waiting.append((open_issues[number], days))
    digest.waiting = sorted(waiting, key=lambda w: (-w[1], w[0]["number"]))[:SECTION_LIMIT]

    pairs: dict[frozenset, tuple[int, int, float]] = {}
    for number in (n for n in open_numbers if open_issues[n]["created_at"] >= window_start):
        for c in find_candidates(store, model, number, cfg.duplicates, cfg.exclude_labels, now, (numbers, vectors)):
            if c.state == "open":
                pairs.setdefault(frozenset((number, c.number)), (number, c.number, c.score))
    digest.open_duplicates = sorted(pairs.values(), key=lambda p: -p[2])[:SECTION_LIMIT]
    return digest


def _issue(issue: dict) -> str:
    return f"#{issue['number']} {sanitize(issue['title'], limit=100)}"


def _numbers(numbers: list[int], limit: int = 8) -> str:
    shown = ", ".join(f"#{n}" for n in sorted(numbers)[:limit])
    return shown + (f" and {len(numbers) - limit} more" if len(numbers) > limit else "")


def render_digest(repo: str, digest: Digest, now: datetime) -> str:
    w = digest.window_days
    sections = {
        "New themes": [
            f"- **{sanitize(t.name, limit=60)}**: {len(t.numbers)} open issues, {t.new} opened in the last {w} days. {_numbers(t.numbers)}"
            for t in digest.new_themes
        ],
        "Growing themes": [
            f"- **{sanitize(t.name, limit=60)}**: {t.new} opened in the last {w} days, {t.previous} in the {w} days before. {_numbers(t.numbers)}"
            for t in digest.growing_themes
        ],
        "Most-wanted, no maintainer reply": [f"- {_issue(i)}: {i['reactions_total']} reactions" for i in digest.most_wanted],
        "Waiting on maintainers": [f"- {_issue(i)}: last comment {days} days ago" for i, days in digest.waiting],
        "Likely duplicates still open": [
            f"- #{new} may duplicate #{old} (similarity {score:.2f})" for new, old, score in digest.open_duplicates
        ],
    }
    lines = [
        f"# Triage digest – {now:%Y-%m-%d}",
        "",
        f"{repo}: open issues over the last {w} days, compiled by issue-triage. Nothing was changed automatically.",
    ]
    for heading, items in sections.items():
        lines += ["", f"## {heading}", "", *(items or ["None this week."])]
    return "\n".join(lines) + "\n"
