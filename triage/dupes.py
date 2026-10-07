"""Find likely duplicates of an issue by cosine similarity over the index."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterator

import numpy as np

from triage.config import DuplicatesConfig
from triage.store import Store
from triage.sync import iso


@dataclass
class Candidate:
    number: int
    title: str
    html_url: str
    state: str
    score: float
    reason: str | None = None


class NotInIndex(LookupError):
    """The issue is not in the index (a pull request, or not synced yet)."""


def ranked(scores: np.ndarray, threshold: float) -> Iterator[tuple[int, float]]:
    """Positions whose score is at least threshold, best first. Sorts only the hits, not the whole index."""
    hits = np.flatnonzero(scores >= threshold)
    for j in hits[np.argsort(-scores[hits], kind="stable")]:
        yield int(j), float(scores[j])


def find_candidates(
    store: Store, model: str, number: int, cfg: DuplicatesConfig, exclude_labels: list[str], now: datetime
) -> list[Candidate]:
    numbers, vectors = store.matrix(model)
    hits = np.flatnonzero(numbers == number)
    if hits.size == 0:
        raise NotInIndex(f"#{number} is not in the index: it may be a pull request, or it has not been synced yet")
    # ponytail: exact brute-force search; fine up to ~1M issues, add an ANN index only if latency demands it
    # Only issues created before the target can be what it duplicates (matrix is ordered by creation time).
    position = int(hits[0])
    scores = vectors[:position] @ vectors[position]
    cutoff = iso(now - timedelta(days=cfg.closed_window_days))
    excluded = set(exclude_labels)
    found: list[Candidate] = []
    for j, score in ranked(scores, cfg.threshold):
        other = int(numbers[j])
        issue = store.issue(other)
        if issue["state"] == "closed" and (issue["closed_at"] or "") < cutoff:
            continue
        if excluded.intersection(issue["labels"]):
            continue
        found.append(Candidate(other, issue["title"], issue["html_url"], issue["state"], round(score, 3)))
        if len(found) == cfg.max_candidates:
            break
    return found
