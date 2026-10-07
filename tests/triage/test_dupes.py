from datetime import datetime, timezone

import pytest

from tests.triage.helpers import WordHashEmbedder, gh_issue
from triage.config import DuplicatesConfig
from triage.dupes import NotInIndex, find_candidates
from triage.embed import embed_pending

NOW = datetime(2026, 6, 1, tzinfo=timezone.utc)
CFG = DuplicatesConfig(threshold=0.5, max_candidates=3, closed_window_days=180)


def index(store, issues):
    embedder = WordHashEmbedder()
    store.upsert_issues(issues)
    embed_pending(store, embedder)
    return embedder.name


def base_issues(**third):
    return [
        gh_issue(1, "App crashes when opening settings on Windows"),
        gh_issue(2, "Crash when opening settings on Windows 11", created="2026-01-09T00:00:00Z"),
        gh_issue(3, "Settings crash on Windows", **third),
        gh_issue(4, "Add dark theme to editor"),
    ]


def test_returns_similar_issues_above_threshold_best_first(store):
    model = index(store, base_issues())
    found = find_candidates(store, model, 2, CFG, [], NOW)
    assert [c.number for c in found] == [3, 1]
    assert found[0].score >= found[1].score >= 0.5
    assert found[0].html_url.endswith("/issues/3")


def test_skips_issues_closed_before_the_window_but_keeps_recent_ones(store):
    model = index(store, base_issues(state="closed", closed="2025-01-01T00:00:00Z"))
    assert [c.number for c in find_candidates(store, model, 2, CFG, [], NOW)] == [1]
    model = index(store, base_issues(state="closed", closed="2026-05-01T00:00:00Z"))
    assert [c.number for c in find_candidates(store, model, 2, CFG, [], NOW)] == [3, 1]


def test_skips_excluded_labels(store):
    model = index(store, base_issues(labels=["wontfix"]))
    assert [c.number for c in find_candidates(store, model, 2, CFG, ["wontfix"], NOW)] == [1]


def test_respects_max_candidates(store):
    model = index(store, base_issues())
    cfg = DuplicatesConfig(threshold=0.5, max_candidates=1)
    assert [c.number for c in find_candidates(store, model, 2, cfg, [], NOW)] == [3]


def test_nothing_above_threshold_returns_empty(store):
    model = index(store, base_issues())
    assert find_candidates(store, model, 4, CFG, [], NOW) == []


def test_missing_issue_raises_clear_error(store):
    model = index(store, base_issues())
    with pytest.raises(NotInIndex, match="#99"):
        find_candidates(store, model, 99, CFG, [], NOW)


def test_only_issues_created_before_the_target_are_candidates(store):
    model = index(store, base_issues())
    assert find_candidates(store, model, 1, CFG, [], NOW) == []
