import json
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from tests.triage.helpers import FakeClient, FakeGitHub, WordHashEmbedder, gh_issue
from triage.commands import check_duplicates
from triage.config import Config, DuplicatesConfig, LLMConfig
from triage.dupes import NotInIndex
from triage.llm import Confirmer

NOW = datetime(2026, 6, 1, tzinfo=timezone.utc)
ISSUES = [
    gh_issue(1, "App crashes when opening settings on Windows"),
    gh_issue(2, "Crash when opening settings on Windows 11"),
    gh_issue(3, "Add dark theme to editor"),
    gh_issue(4, "Fix typo", pr=True),
]


def config(dry_run):
    return Config(dry_run=dry_run, duplicates=DuplicatesConfig(threshold=0.5))


def run(fake, store, cfg, number=2, confirmer=None):
    return check_duplicates(fake.client(), store, WordHashEmbedder(), cfg, "o/r", number, NOW, confirmer)


def test_dry_run_reports_without_posting(store):
    fake = FakeGitHub(issues=ISSUES)
    outcome = run(fake, store, config(dry_run=True))
    assert outcome.action == "dry-run"
    assert [c.number for c in outcome.candidates] == [1]
    assert fake.issue_comments == {}


def test_posts_comment_and_label_when_dry_run_is_off(store):
    fake = FakeGitHub(issues=ISSUES)
    outcome = run(fake, store, config(dry_run=False))
    assert outcome.action == "created"
    body = fake.issue_comments[2][0]["body"]
    assert "#1" in body and "Related issues" in body and "duplicate of" not in body
    assert 2 not in fake.labels  # no LLM: related issues only, never a duplicate claim or label


def test_rerun_updates_instead_of_posting_twice(store):
    fake = FakeGitHub(issues=ISSUES)
    run(fake, store, config(dry_run=False))
    assert run(fake, store, config(dry_run=False)).action == "updated"
    assert len(fake.issue_comments[2]) == 1


def test_no_candidates_posts_nothing(store):
    fake = FakeGitHub(issues=ISSUES)
    outcome = run(fake, store, config(dry_run=False), number=3)
    assert outcome.action == "none"
    assert fake.issue_comments == {}


def test_disabled_skips_search(store):
    cfg = replace(config(dry_run=False), duplicates=DuplicatesConfig(enabled=False))
    assert run(FakeGitHub(issues=ISSUES), store, cfg).action == "disabled"


def test_llm_rejection_lists_related_issues_without_label(store):
    fake = FakeGitHub(issues=ISSUES)
    confirmer = Confirmer(LLMConfig(base_url="http://x", model="m"), client=FakeClient(json.dumps({"duplicates": []})))
    outcome = run(fake, store, config(dry_run=False), confirmer=confirmer)
    assert outcome.action == "created" and not any(c.confirmed for c in outcome.candidates)
    assert 2 not in fake.labels


def test_llm_confirmed_duplicate_is_flagged_and_labelled(store):
    fake = FakeGitHub(issues=ISSUES)
    reply = json.dumps({"duplicates": [{"number": 1, "reason": "Same settings crash"}]})
    confirmer = Confirmer(LLMConfig(base_url="http://x", model="m"), client=FakeClient(reply))
    outcome = run(fake, store, config(dry_run=False), confirmer=confirmer)
    assert [c.confirmed for c in outcome.candidates] == [True]
    assert "may be a duplicate of" in fake.issue_comments[2][0]["body"]
    assert fake.labels[2] == ["possible-duplicate"]


def test_pull_request_number_gives_clear_error(store):
    with pytest.raises(NotInIndex, match="#4"):
        run(FakeGitHub(issues=ISSUES), store, config(dry_run=True), number=4)
