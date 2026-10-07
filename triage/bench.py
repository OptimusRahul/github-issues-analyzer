"""Replay issues already closed as duplicates to measure duplicate detection."""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from triage.dupes import Candidate, ranked
from triage.store import Store

DUP_REF = re.compile(r"duplicate of\s+(?:#|https://github\.com/[\w.-]+/[\w.-]+/issues/)(\d+)", re.IGNORECASE)
THRESHOLDS = [round(0.50 + 0.01 * i, 2) for i in range(50)]
REPORT_THRESHOLDS = {round(0.50 + 0.05 * i, 2) for i in range(10)}
MAX_FALSE_FLAG_RATE = 0.10


def is_closed_duplicate(issue: dict) -> bool:
    if issue["state"] != "closed":
        return False
    return issue.get("state_reason") == "duplicate" or any("duplicate" in label.lower() for label in issue["labels"])


def find_original(texts: list[str]) -> int | None:
    for text in texts:
        match = DUP_REF.search(text or "")
        if match:
            return int(match.group(1))
    return None


def ground_truth(store: Store, fetch_comments: Callable[[int], list[dict]], max_pairs: int) -> list[tuple[int, int]]:
    """(duplicate, original) pairs, newest duplicates first. Comments missing from the index are fetched."""
    pairs: list[tuple[int, int]] = []
    for issue in reversed(store.issues()):
        if len(pairs) >= max_pairs:
            break
        if not is_closed_duplicate(issue):
            continue
        comments = store.comments_for(issue["number"]) or fetch_comments(issue["number"])
        original_number = find_original([c["body"] for c in comments] + [issue["body"]])
        original = store.issue(original_number) if original_number else None
        if original and original_number != issue["number"] and original["created_at"] < issue["created_at"]:
            pairs.append((issue["number"], original_number))
    return pairs


@dataclass
class ThresholdResult:
    threshold: float
    recall: float
    false_flag_rate: float


@dataclass
class BenchResult:
    model: str
    pairs: int
    non_duplicates: int
    recall_at_3: float
    thresholds: list[ThresholdResult]
    recommended: ThresholdResult | None
    sample: list[int] = field(default_factory=list, repr=False)


def evaluate(
    numbers: np.ndarray, vectors: np.ndarray, pairs: list[tuple[int, int]], model: str, sample_size: int = 500, seed: int = 0
) -> BenchResult:
    """numbers and vectors must be ordered by creation time (as Store.matrix returns them)."""
    position = {int(n): i for i, n in enumerate(numbers)}
    pairs = [(d, o) for d, o in pairs if d in position and o in position]
    duplicates = {d for d, _ in pairs}

    # Score of the original when it is in the top 3 of issues created earlier, else None.
    hit_scores: list[float | None] = []
    for dup, original in pairs:
        p = position[dup]
        scores = vectors[:p] @ vectors[p]
        k = min(3, p)
        top = np.argpartition(-scores, k - 1)[:k]
        hit_scores.append(float(scores[position[original]]) if position[original] in top else None)

    eligible = [i for i, n in enumerate(numbers) if i > 0 and int(n) not in duplicates]
    sample = random.Random(seed).sample(eligible, min(sample_size, len(eligible)))
    best_scores = [float((vectors[:p] @ vectors[p]).max()) for p in sample]

    results = []
    for t in THRESHOLDS:
        recall = sum(1 for s in hit_scores if s is not None and s >= t) / len(pairs) if pairs else 0.0
        false_flags = sum(1 for s in best_scores if s >= t) / len(best_scores) if best_scores else 0.0
        results.append(ThresholdResult(t, recall, false_flags))
    acceptable = [r for r in results if r.false_flag_rate <= MAX_FALSE_FLAG_RATE]
    recommended = max(acceptable, key=lambda r: (r.recall, r.threshold)) if acceptable else None
    recall_at_3 = sum(1 for s in hit_scores if s is not None) / len(pairs) if pairs else 0.0
    return BenchResult(model, len(pairs), len(sample), recall_at_3, results, recommended, sample)


def _pct(x: float) -> str:
    return f"{x:.0%}"


def render_report(repo: str, result: BenchResult, llm=None) -> str:
    lines = [
        f"# Duplicate benchmark: {repo}",
        "",
        f"- Embedding model: `{result.model}`",
        f"- Duplicate pairs: {result.pairs}",
        f"- Non-duplicate sample: {result.non_duplicates}",
        f"- Recall@3 with no threshold: {_pct(result.recall_at_3)}",
    ]
    if result.recommended:
        r = result.recommended
        lines.append(
            f"- Recommended threshold: **{r.threshold:.2f}** "
            f"(recall@3 {_pct(r.recall)}, false flags {_pct(r.false_flag_rate)})"
        )
    else:
        lines.append(f"- No threshold keeps false flags at or below {_pct(MAX_FALSE_FLAG_RATE)}.")
    shown = [
        r for r in result.thresholds
        if r.threshold in REPORT_THRESHOLDS or (result.recommended and r.threshold == result.recommended.threshold)
    ]
    lines += ["", "| Threshold | Recall@3 | False flags |", "|---|---|---|"]
    lines += [f"| {r.threshold:.2f} | {_pct(r.recall)} | {_pct(r.false_flag_rate)} |" for r in shown]
    if llm is not None:
        lines += [
            "",
            f"## With LLM confirmation at {llm.threshold:.2f}",
            "",
            f"- Pairs checked: {llm.pairs_checked}, recall@3: {_pct(llm.recall)}",
            f"- Non-duplicates checked: {llm.samples_checked}, false flags: {_pct(llm.false_flag_rate)}",
            f"- LLM calls: {llm.calls}",
        ]
    return "\n".join(lines) + "\n"


@dataclass
class LLMResult:
    threshold: float
    pairs_checked: int
    recall: float
    samples_checked: int
    false_flag_rate: float
    calls: int


def _top_candidates(store: Store, numbers: np.ndarray, vectors: np.ndarray, p: int, threshold: float) -> list[Candidate]:
    found = []
    for j, score in ranked(vectors[:p] @ vectors[p], threshold):
        issue = store.issue(int(numbers[j]))
        found.append(Candidate(issue["number"], issue["title"], issue["html_url"], issue["state"], score))
        if len(found) == 3:
            break
    return found


def evaluate_with_llm(
    store: Store,
    numbers: np.ndarray,
    vectors: np.ndarray,
    pairs: list[tuple[int, int]],
    sample: list[int],
    threshold: float,
    confirmer,
    max_calls: int,
) -> LLMResult:
    """Re-run pairs and the non-duplicate sample with LLM confirmation, spending at most max_calls (half each)."""
    position = {int(n): i for i, n in enumerate(numbers)}
    hits = pairs_checked = 0
    for dup, original in pairs:
        if confirmer.calls >= max_calls // 2 or dup not in position:
            break
        candidates = _top_candidates(store, numbers, vectors, position[dup], threshold)
        pairs_checked += 1
        if any(c.number == original for c in confirmer.confirm(store.issue(dup), candidates, store.issue)):
            hits += 1
    flags = samples_checked = 0
    for p in sample:
        if confirmer.calls >= max_calls:
            break
        candidates = _top_candidates(store, numbers, vectors, p, threshold)
        samples_checked += 1
        if confirmer.confirm(store.issue(int(numbers[p])), candidates, store.issue):
            flags += 1
    return LLMResult(
        threshold,
        pairs_checked,
        hits / pairs_checked if pairs_checked else 0.0,
        samples_checked,
        flags / samples_checked if samples_checked else 0.0,
        confirmer.calls,
    )
