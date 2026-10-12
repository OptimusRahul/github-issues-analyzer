import json
from datetime import datetime, timezone

from tests.triage.helpers import FakeClient, FakeGitHub, WordHashEmbedder, gh_issue
from triage.commands import check_labels
from triage.config import Config, LabelsConfig, LLMConfig
from triage.embed import embed_pending
from triage.labels import evaluate_labels, render_labels_comment, suggest_labels
from triage.llm import ChatModel

NOW = datetime(2026, 6, 1, tzinfo=timezone.utc)
CFG = LabelsConfig(enabled=True, neighbors=5, min_share=0.3, max_labels=2, similar_threshold=0.3)
REPO_LABELS = ["bug", "windows", "enhancement", "ui", "possible-duplicate"]
ISSUES = [
    gh_issue(1, "Crash when opening settings on Windows", labels=["bug", "windows"], created="2026-05-10T00:00:00Z"),
    gh_issue(2, "Settings window crash on Windows 11", labels=["bug", "windows", "possible-duplicate"], created="2026-05-11T00:00:00Z"),
    gh_issue(3, "Add dark theme to editor", labels=["enhancement", "ui"], created="2026-05-12T00:00:00Z"),
    gh_issue(4, "Crash opening settings on Windows laptop", created="2026-05-20T00:00:00Z", reactions=4),
]


def index(store, issues=ISSUES):
    embedder = WordHashEmbedder()
    store.upsert_issues(issues)
    embed_pending(store, embedder)
    return embedder.name


def test_suggests_labels_of_similar_earlier_issues(store):
    model = index(store)
    s = suggest_labels(store, model, 4, REPO_LABELS, CFG, NOW, ignore=["possible-duplicate"])
    assert s.labels == ["bug", "windows"]
    assert s.similar_recent == 2  # issues 1 and 2, opened within 30 days
    assert s.priority == "medium"


def test_never_suggests_labels_missing_from_the_repo(store):
    model = index(store)
    s = suggest_labels(store, model, 4, ["windows"], CFG, NOW)
    assert s.labels == ["windows"]


def test_llm_picks_only_existing_labels_and_falls_back_to_votes(store):
    model = index(store)
    chat = ChatModel(LLMConfig(base_url="http://x", model="m"), client=FakeClient(json.dumps({"labels": ["bug", "made-up"]}), json.dumps({"labels": ["windows"]})))
    s = suggest_labels(store, model, 4, REPO_LABELS, CFG, NOW, chat=chat)
    assert s.labels == ["windows"]
    assert "untrusted" in chat.client.calls[0]["messages"][0]["content"]
    chat = ChatModel(LLMConfig(base_url="http://x", model="m"), client=FakeClient("no", "no"))
    assert suggest_labels(store, model, 4, REPO_LABELS, CFG, NOW, chat=chat).labels == ["bug", "windows"]


def test_comment_lists_labels_and_priority():
    from triage.labels import LabelSuggestion

    body = render_labels_comment(LabelSuggestion(["bug"], "high", 3), applied=False)
    assert body.startswith("<!-- issue-triage:labels -->")
    assert "`bug`" in body and "high" in body and "3 similar" in body


def test_check_labels_dry_run_then_apply(store):
    fake = FakeGitHub(issues=ISSUES)
    fake.repo_labels = REPO_LABELS
    cfg = Config(dry_run=True, labels=CFG)
    outcome = check_labels(fake.client(), store, WordHashEmbedder(), cfg, "o/r", 4, NOW)
    assert outcome.action == "dry-run" and outcome.suggestion.labels == ["bug", "windows"]
    assert fake.issue_comments == {}

    cfg = Config(dry_run=False, labels=LabelsConfig(enabled=True, apply=True, neighbors=5, max_labels=2))
    outcome = check_labels(fake.client(), store, WordHashEmbedder(), cfg, "o/r", 4, NOW)
    assert outcome.action == "created"
    assert fake.labels[4] == ["bug", "windows"]
    assert fake.issue_comments[4][0]["body"].startswith("<!-- issue-triage:labels -->")


def test_check_labels_posts_without_applying_by_default(store):
    fake = FakeGitHub(issues=ISSUES)
    fake.repo_labels = REPO_LABELS
    cfg = Config(dry_run=False, labels=CFG)
    assert check_labels(fake.client(), store, WordHashEmbedder(), cfg, "o/r", 4, NOW).action == "created"
    assert 4 not in fake.labels


def test_check_labels_disabled_by_default(store):
    assert check_labels(FakeGitHub().client(), store, WordHashEmbedder(), Config(), "o/r", 4, NOW).action == "disabled"


def test_evaluate_labels_scores_against_applied_labels(store):
    issues = ISSUES[:3] + [gh_issue(4, "Crash opening settings on Windows laptop", labels=["bug"], created="2026-05-20T00:00:00Z")]
    model = index(store, issues)
    result = evaluate_labels(store, model, REPO_LABELS, CFG, ignore=["possible-duplicate"], sample_size=10)
    assert result.issues == 3  # issue 1 has no earlier issue to learn from
    assert 0 < result.precision <= 1 and 0 < result.recall <= 1
