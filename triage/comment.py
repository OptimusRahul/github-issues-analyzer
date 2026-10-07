"""Render the duplicate-flag comment and post it, updating the tool's own earlier comment if present."""

from __future__ import annotations

from triage.dupes import Candidate
from triage.github import GitHubClient
from triage.text import sanitize

MARKER = "<!-- issue-triage:duplicates -->"


def render_comment(candidates: list[Candidate]) -> str:
    lines = [MARKER, "This issue may be a duplicate of:", ""]
    for c in candidates:
        line = f"- #{c.number} {sanitize(c.title, limit=120)}"
        if c.reason:
            line += f" ({c.reason})"
        lines.append(line)
    lines += ["", "<sub>Flagged by issue-triage. It never closes issues; a maintainer decides.</sub>"]
    return "\n".join(lines)


def post_or_update(gh: GitHubClient, repo: str, number: int, body: str, label: str | None) -> str:
    me = gh.viewer_login()
    existing = next(
        (
            c for c in gh.issue_comments(repo, number)
            if MARKER in (c.get("body") or "") and ((c.get("user") or {}).get("login") or "").lower() == me
        ),
        None,
    )
    if existing:
        gh.update_comment(repo, existing["id"], body)
        action = "updated"
    else:
        gh.create_comment(repo, number, body)
        action = "created"
    if label:
        gh.add_labels(repo, number, [label])
    return action
