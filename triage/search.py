"""Combined keyword and vector search over the index."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import numpy as np

from triage.embed import Embedder, normalize
from triage.store import Store

RRF_K = 60  # reciprocal rank fusion constant
POOL = 100  # candidates taken from each ranking before fusion


@dataclass
class Hit:
    number: int
    title: str
    html_url: str
    state: str
    score: float


def _allowed(store: Store, state: str | None, labels: list[str] | None, since: str | None) -> set[int]:
    required = set(labels or [])
    return {
        number
        for number, issue_state, issue_labels, created_at in store.filter_rows()
        if (state is None or issue_state == state)
        and required.issubset(issue_labels)
        and (since is None or created_at >= since)
    }


def hybrid_search(
    store: Store,
    embedder: Embedder,
    query: str,
    limit: int = 10,
    state: str | None = None,
    labels: list[str] | None = None,
    since: str | None = None,
) -> list[Hit]:
    """Issues matching the query, best first. Filters apply before ranking."""
    allowed = _allowed(store, state, labels, since)
    rankings: list[list[int]] = []

    numbers, vectors = store.matrix(embedder.name)
    if numbers.size:
        scores = vectors @ normalize(embedder.embed([query]))[0]
        mask = np.fromiter((int(n) in allowed for n in numbers), dtype=bool, count=numbers.size)
        order = np.flatnonzero(mask)[np.argsort(-scores[mask], kind="stable")][:POOL]
        rankings.append([int(numbers[j]) for j in order])
    rankings.append([n for n in store.keyword_search(query, POOL * 5) if n in allowed][:POOL])

    fused: dict[int, float] = defaultdict(float)
    for ranking in rankings:
        for rank, number in enumerate(ranking, start=1):
            fused[number] += 1.0 / (RRF_K + rank)
    hits = []
    for number in sorted(fused, key=lambda n: (-fused[n], n))[:limit]:
        issue = store.issue(number)
        hits.append(Hit(number, issue["title"], issue["html_url"], issue["state"], round(fused[number], 4)))
    return hits
