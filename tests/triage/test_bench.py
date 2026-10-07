import numpy as np
import pytest

from tests.triage.helpers import gh_comment, gh_issue
from triage.bench import (
    BenchResult,
    ThresholdResult,
    evaluate,
    evaluate_with_llm,
    find_original,
    ground_truth,
    is_closed_duplicate,
    render_report,
)
from triage.store import Store


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "index.sqlite")
    yield s
    s.close()


def test_find_original_parses_hash_and_url_forms():
    assert find_original(["thanks", "Duplicate of #12"]) == 12
    assert find_original(["duplicate of https://github.com/o/r/issues/34"]) == 34
    assert find_original(["no reference", None]) is None


def test_is_closed_duplicate_uses_state_reason_or_label():
    assert is_closed_duplicate({"state": "closed", "state_reason": "duplicate", "labels": []})
    assert is_closed_duplicate({"state": "closed", "state_reason": "not_planned", "labels": ["*duplicate"]})
    assert not is_closed_duplicate({"state": "open", "state_reason": None, "labels": ["duplicate"]})


def test_ground_truth_pairs_only_earlier_originals_and_fetches_missing_comments(store):
    store.upsert_issues([
        gh_issue(1, created="2026-01-01T00:00:00Z"),
        gh_issue(2, created="2026-01-02T00:00:00Z", state="closed", labels=["duplicate"]),
        gh_issue(3, created="2026-01-03T00:00:00Z", state="closed", state_reason="duplicate"),
        gh_issue(4, created="2026-01-04T00:00:00Z", state="closed", labels=["duplicate"]),
    ])
    store.upsert_comments([gh_comment(10, 2, "Duplicate of #1"), gh_comment(11, 4, "Duplicate of #99")])
    fetched = []

    def fetch(number):
        fetched.append(number)
        return [{"body": "Duplicate of #4"}]  # points at a later issue, so it is not a valid pair

    assert ground_truth(store, fetch, max_pairs=10) == [(2, 1)]
    assert fetched == [3]


def unit(*xs):
    v = np.array(xs, dtype=np.float32)
    return v / np.linalg.norm(v)


def toy():
    numbers = np.array([1, 2, 3, 4, 5, 6])
    vectors = np.stack([
        unit(1, 0, 0, 0),        # 1
        unit(0, 1, 0, 0),        # 2
        unit(0, 0, 1, 0),        # 3
        unit(1, 0.1, 0, 0),      # 4: duplicate of 1, score ~0.995
        unit(0, 0, 0, 1),        # 5: unrelated
        unit(0, 1, 0, 1),        # 6: half-similar to 2 and 5, best score ~0.707
    ])
    return numbers, vectors


def test_evaluate_measures_recall_and_false_flags():
    numbers, vectors = toy()
    result = evaluate(numbers, vectors, [(4, 1)], "m", sample_size=10)
    assert result.pairs == 1
    assert result.recall_at_3 == 1.0
    by_t = {r.threshold: r for r in result.thresholds}
    assert by_t[0.99].recall == 1.0
    assert by_t[0.70].false_flag_rate > 0
    assert by_t[0.80].false_flag_rate == 0
    assert result.recommended.threshold == 0.99


def test_evaluate_drops_pairs_missing_from_index():
    numbers, vectors = toy()
    assert evaluate(numbers, vectors, [(4, 77)], "m").pairs == 0


def test_report_has_summary_table_and_recommendation():
    result = BenchResult(
        model="local:x", pairs=10, non_duplicates=50, recall_at_3=0.8,
        thresholds=[ThresholdResult(0.80, 0.7, 0.12), ThresholdResult(0.85, 0.6, 0.05)],
        recommended=ThresholdResult(0.85, 0.6, 0.05), sample=[],
    )
    report = render_report("o/r", result)
    assert "# Duplicate benchmark: o/r" in report
    assert "Recommended threshold: **0.85**" in report
    assert "| 0.85 | 60% | 5% |" in report


def test_report_when_no_threshold_meets_the_limit():
    result = BenchResult("m", 1, 1, 0.0, [ThresholdResult(0.5, 0.0, 0.5)], None, [])
    assert "No threshold keeps false flags at or below 10%" in render_report("o/r", result)


class FakeConfirmer:
    """Confirms a candidate only if it is in `accept`; counts calls."""

    def __init__(self, accept):
        self.accept = accept
        self.calls = 0

    def confirm(self, issue, candidates, lookup):
        self.calls += 1
        return [c for c in candidates if (issue["number"], c.number) in self.accept]


def test_llm_evaluation_counts_confirmed_originals_and_rejected_false_flags(store):
    store.upsert_issues([gh_issue(n, f"issue {n}", created=f"2026-01-0{n}T00:00:00Z") for n in range(1, 7)])
    numbers, vectors = toy()
    confirmer = FakeConfirmer(accept={(4, 1)})
    result = evaluate_with_llm(store, numbers, vectors, [(4, 1)], sample=[5], threshold=0.70, confirmer=confirmer, max_calls=10)
    assert (result.pairs_checked, result.recall) == (1, 1.0)
    assert (result.samples_checked, result.false_flag_rate) == (1, 0.0)
    assert result.calls == 2


def test_llm_evaluation_stops_at_call_budget(store):
    store.upsert_issues([gh_issue(n, f"issue {n}", created=f"2026-01-0{n}T00:00:00Z") for n in range(1, 7)])
    numbers, vectors = toy()
    result = evaluate_with_llm(store, numbers, vectors, [(4, 1)], sample=[5], threshold=0.70, confirmer=FakeConfirmer(set()), max_calls=0)
    assert result.calls == 0 and result.pairs_checked == 0
