import json
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from tests.triage.helpers import FakeGitHub, WordHashEmbedder, gh_issue
from tests.triage.test_llm import FakeClient
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
    assert "#1" in fake.issue_comments[2][0]["body"]
    assert fake.labels[2] == ["possible-duplicate"]


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


def test_llm_rejection_means_nothing_is_posted(store):
    fake = FakeGitHub(issues=ISSUES)
    confirmer = Confirmer(LLMConfig(base_url="http://x", model="m"), client=FakeClient(json.dumps({"duplicates": []})))
    outcome = run(fake, store, config(dry_run=False), confirmer=confirmer)
    assert outcome.action == "none"
    assert fake.issue_comments == {}


def test_pull_request_number_gives_clear_error(store):
    with pytest.raises(NotInIndex, match="#4"):
        run(FakeGitHub(issues=ISSUES), store, config(dry_run=True), number=4)
