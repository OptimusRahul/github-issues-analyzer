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


def _is_own(comment: dict, me: str | None) -> bool:
    if MARKER not in (comment.get("body") or ""):
        return False
    user = comment.get("user") or {}
    if me is not None:
        return (user.get("login") or "").lower() == me
    # App and Actions tokens cannot look up their login; they post as a Bot account, which no person can be.
    return user.get("type") == "Bot"


def post_or_update(gh: GitHubClient, repo: str, number: int, body: str, label: str | None) -> str:
    me = gh.viewer_login()
    existing = next((c for c in gh.issue_comments(repo, number) if _is_own(c, me)), None)
    if existing:
        gh.update_comment(repo, existing["id"], body)
        action = "updated"
    else:
        gh.create_comment(repo, number, body)
        action = "created"
    if label:
        gh.add_labels(repo, number, [label])
    return action
