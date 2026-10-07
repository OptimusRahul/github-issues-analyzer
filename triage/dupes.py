"""Find likely duplicates of an issue by cosine similarity over the index."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

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


def find_candidates(
    store: Store, model: str, number: int, cfg: DuplicatesConfig, exclude_labels: list[str], now: datetime
) -> list[Candidate]:
    numbers, vectors = store.matrix(model)
    hits = np.flatnonzero(numbers == number)
    if hits.size == 0:
        raise NotInIndex(f"#{number} is not in the index: it may be a pull request, or it has not been synced yet")
    # ponytail: exact brute-force search; fine up to ~1M issues, add an ANN index only if latency demands it
    scores = vectors @ vectors[hits[0]]
    cutoff = iso(now - timedelta(days=cfg.closed_window_days))
    excluded = set(exclude_labels)
    found: list[Candidate] = []
    for j in np.argsort(-scores, kind="stable"):
        score = float(scores[j])
        if score < cfg.threshold:
            break
        other = int(numbers[j])
        if other == number:
            continue
        issue = store.issue(other)
        if issue["state"] == "closed" and (issue["closed_at"] or "") < cutoff:
            continue
        if excluded.intersection(issue["labels"]):
            continue
        found.append(Candidate(other, issue["title"], issue["html_url"], issue["state"], round(score, 3)))
        if len(found) == cfg.max_candidates:
            break
    return found
