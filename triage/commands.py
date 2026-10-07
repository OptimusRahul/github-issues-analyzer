"""Operations shared by the CLI, and later by the GitHub Action and the server."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from triage.comment import post_or_update, render_comment
from triage.config import Config
from triage.dupes import Candidate, find_candidates
from triage.embed import Embedder, embed_pending
from triage.github import GitHubClient
from triage.llm import Confirmer
from triage.store import Store
from triage.sync import sync_repo


@dataclass
class DupesOutcome:
    candidates: list[Candidate] = field(default_factory=list)
    action: str = "none"  # disabled | none | dry-run | created | updated


def check_duplicates(
    gh: GitHubClient,
    store: Store,
    embedder: Embedder,
    cfg: Config,
    repo: str,
    number: int,
    now: datetime,
    confirmer: Confirmer | None = None,
) -> DupesOutcome:
    if not cfg.duplicates.enabled:
        return DupesOutcome(action="disabled")
    sync_repo(gh, store, repo, now, cfg.comments_window_days)
    embed_pending(store, embedder)
    candidates = find_candidates(store, embedder.name, number, cfg.duplicates, cfg.exclude_labels, now)
    if candidates and confirmer is not None:
        candidates = confirmer.confirm(store.issue(number), candidates, store.issue)
    if not candidates:
        return DupesOutcome(action="none")
    if cfg.dry_run:
        return DupesOutcome(candidates, "dry-run")
    action = post_or_update(gh, repo, number, render_comment(candidates), cfg.duplicates.label)
    return DupesOutcome(candidates, action)
