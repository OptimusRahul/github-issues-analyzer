"""Render the duplicate-flag comment and post comments, updating the tool's own earlier comment if present."""

from __future__ import annotations

from triage.dupes import Candidate
from triage.github import GitHubClient
from triage.text import sanitize

MARKER = "<!-- issue-triage:duplicates -->"


def _line(c: Candidate) -> str:
    line = f"- #{c.number} {sanitize(c.title, limit=120)}"
    return line + (f" ({c.reason})" if c.reason else "")


def render_comment(candidates: list[Candidate]) -> str:
    """Confirmed candidates are called possible duplicates; the rest are only listed as related issues."""
    confirmed = [c for c in candidates if c.confirmed]
    related = [c for c in candidates if not c.confirmed]
    lines = [MARKER]
    if confirmed:
        lines += ["This issue may be a duplicate of:", "", *map(_line, confirmed), ""]
    if related:
        lines += ["Related issues that may help:" if not confirmed else "Related issues:", "", *map(_line, related), ""]
    lines.append("<sub>Found by issue-triage. It never closes issues; a maintainer decides.</sub>")
    return "\n".join(lines)


def _is_own(comment: dict, me: str | None, marker: str) -> bool:
    if marker not in (comment.get("body") or ""):
        return False
    user = comment.get("user") or {}
    if me is not None:
        return (user.get("login") or "").lower() == me
    # App and Actions tokens cannot look up their login; they post as a Bot account, which no person can be.
    return user.get("type") == "Bot"


def post_or_update(gh: GitHubClient, repo: str, number: int, body: str, labels: list[str]) -> str:
    """Post `body`, or update the tool's earlier comment that starts with the same marker line, then add labels."""
    me = gh.viewer_login()
    marker = body.split("\n", 1)[0]
    existing = next((c for c in gh.issue_comments(repo, number) if _is_own(c, me, marker)), None)
    if existing:
        gh.update_comment(repo, existing["id"], body)
        action = "updated"
    else:
        gh.create_comment(repo, number, body)
        action = "created"
    if labels:
        gh.add_labels(repo, number, labels)
    return action
