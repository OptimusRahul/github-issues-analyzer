"""Incremental, resumable sync of one repository's issues and comments into the Store."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from triage.github import GitHubClient
from triage.store import Store

ISO_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime(ISO_FORMAT)


class IndexMismatch(ValueError):
    """The index file belongs to a different repository."""


@dataclass
class SyncResult:
    issues: int = 0
    comments: int = 0
    pages: int = 0


def _new_cursor(store: Store, now: datetime, comments_window_days: int) -> dict:
    last = store.get_state("last_synced_at")
    window_start = iso(now - timedelta(days=comments_window_days))
    return {
        "phase": "issues",
        "next_url": None,
        "started_at": iso(now),
        "issues_since": last,
        "comments_since": max(last or window_start, window_start),
    }


def _save(store: Store, cursor: dict) -> None:
    store.set_state("cursor", cursor)
    store.commit()


def sync_repo(gh: GitHubClient, store: Store, repo: str, now: datetime, comments_window_days: int = 180) -> SyncResult:
    known = store.get_state("repo")
    if known not in (None, repo):
        raise IndexMismatch(f"This index belongs to {known}, not {repo}")
    store.set_state("repo", repo)

    cursor = store.get_state("cursor") or _new_cursor(store, now, comments_window_days)
    _save(store, cursor)
    result = SyncResult()

    if cursor["phase"] == "issues":
        params = {"state": "all", "sort": "created", "direction": "asc", "per_page": 100}
        if cursor["issues_since"]:
            params["since"] = cursor["issues_since"]
        for page in gh.pages(f"/repos/{repo}/issues", params, cursor["next_url"]):
            result.issues += store.upsert_issues(page.items)
            result.pages += 1
            cursor["next_url"] = page.next_url
            if page.next_url is None:
                cursor["phase"] = "comments"
            _save(store, cursor)

    params = {"sort": "created", "direction": "asc", "per_page": 100, "since": cursor["comments_since"]}
    for page in gh.pages(f"/repos/{repo}/issues/comments", params, cursor["next_url"]):
        result.comments += store.upsert_comments(page.items)
        result.pages += 1
        cursor["next_url"] = page.next_url
        _save(store, cursor)

    store.set_state("last_synced_at", cursor["started_at"])
    store.set_state("cursor", None)
    store.commit()
    return result
