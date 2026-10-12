"""Operations shared by the CLI, and later by the GitHub Action and the server."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from triage.comment import post_or_update, render_comment
from triage.config import Config
from triage.dupes import Candidate, find_candidates
from triage.embed import Embedder, embed_pending
from triage.github import GitHubClient
from triage.labels import LabelSuggestion, render_labels_comment, suggest_labels
from triage.llm import ChatModel, Confirmer
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
    if not candidates:
        return DupesOutcome(action="none")
    if confirmer is not None:
        confirmer.confirm(store.issue(number), candidates, store.issue)  # marks the confirmed ones
        candidates.sort(key=lambda c: not c.confirmed)  # stable: confirmed first, each group best first
    if cfg.dry_run:
        return DupesOutcome(candidates, "dry-run")
    confirmed = any(c.confirmed for c in candidates)
    labels = [cfg.duplicates.label] if cfg.duplicates.label and confirmed else []
    action = post_or_update(gh, repo, number, render_comment(candidates), labels)
    return DupesOutcome(candidates, action)


@dataclass
class LabelsOutcome:
    suggestion: LabelSuggestion | None = None
    action: str = "none"  # disabled | none | dry-run | created | updated


def ignored_labels(cfg: Config) -> list[str]:
    """Labels never suggested: the tool's own duplicate label and GitHub's default duplicate label."""
    return [label for label in (cfg.duplicates.label, "duplicate") if label]


def check_labels(
    gh: GitHubClient,
    store: Store,
    embedder: Embedder,
    cfg: Config,
    repo: str,
    number: int,
    now: datetime,
    chat: ChatModel | None = None,
) -> LabelsOutcome:
    if not cfg.labels.enabled:
        return LabelsOutcome(action="disabled")
    sync_repo(gh, store, repo, now, cfg.comments_window_days)
    embed_pending(store, embedder)
    suggestion = suggest_labels(
        store, embedder.name, number, gh.list_labels(repo), cfg.labels, now, chat, ignored_labels(cfg)
    )
    if not suggestion.labels:
        return LabelsOutcome(suggestion, "none")
    if cfg.dry_run:
        return LabelsOutcome(suggestion, "dry-run")
    apply = cfg.labels.apply
    body = render_labels_comment(suggestion, applied=apply)
    action = post_or_update(gh, repo, number, body, suggestion.labels if apply else [])
    return LabelsOutcome(suggestion, action)
