from datetime import datetime, timezone

import pytest

from tests.triage.helpers import FakeGitHub, gh_comment, gh_issue
from triage.github import GitHubError
from triage.sync import IndexMismatch, sync_repo

NOW = datetime(2026, 6, 1, tzinfo=timezone.utc)
LATER = datetime(2026, 6, 2, tzinfo=timezone.utc)


def issue_requests(fake):
    return [r for r in fake.requests if r.url.path == "/repos/o/r/issues"]


def comment_requests(fake):
    return [r for r in fake.requests if r.url.path == "/repos/o/r/issues/comments"]


def test_first_sync_fetches_all_issues_and_recent_comments(store):
    fake = FakeGitHub(
        issues=[gh_issue(1), gh_issue(2), gh_issue(3, pr=True), gh_issue(4)],
        comments=[gh_comment(10, 1, "hello")],
        per_page=2,
    )
    result = sync_repo(fake.client(), store, "o/r", NOW)
    assert (result.issues, result.comments) == (3, 1)
    assert store.count_issues() == 3
    first = issue_requests(fake)[0].url.params
    assert first["state"] == "all" and first["per_page"] == "100" and "since" not in first
    assert comment_requests(fake)[0].url.params["since"] == "2025-12-03T00:00:00Z"
    assert store.get_state("last_synced_at") == "2026-06-01T00:00:00Z"
    assert store.get_state("cursor") is None


def test_second_sync_only_asks_for_updates_since_last_start(store):
    fake = FakeGitHub(issues=[gh_issue(1)])
    sync_repo(fake.client(), store, "o/r", NOW)
    fake.requests.clear()
    sync_repo(fake.client(), store, "o/r", LATER)
    assert issue_requests(fake)[0].url.params["since"] == "2026-06-01T00:00:00Z"
    assert comment_requests(fake)[0].url.params["since"] == "2026-06-01T00:00:00Z"


def test_resume_after_failure_skips_completed_pages(store):
    fake = FakeGitHub(issues=[gh_issue(1), gh_issue(2), gh_issue(3)], per_page=1)
    fake.fail_once.add("issues:2")
    with pytest.raises(GitHubError):
        sync_repo(fake.client(), store, "o/r", NOW)
    assert store.count_issues() == 1
    fake.requests.clear()
    sync_repo(fake.client(), store, "o/r", NOW)
    pages = [r.url.params.get("page", "1") for r in issue_requests(fake)]
    assert pages == ["2", "3"]
    assert store.count_issues() == 3


def test_index_for_another_repo_is_rejected(store):
    sync_repo(FakeGitHub().client(), store, "o/r", NOW)
    with pytest.raises(IndexMismatch, match="o/r"):
        sync_repo(FakeGitHub(repo="x/y").client(), store, "x/y", NOW)


def test_issue_edited_mid_sync_does_not_push_another_out_of_the_index(store):
    issues = [gh_issue(n, created=f"2026-01-0{n}T00:00:00Z") for n in (1, 2, 3, 4)]
    fake = FakeGitHub(issues=issues, per_page=2)

    def edit_issue_one_after_first_page(request):
        if request.url.path == "/repos/o/r/issues" and request.url.params.get("page", "1") == "1":
            issues[0]["updated_at"] = "2026-06-01T00:00:00Z"

    fake.on_request = edit_issue_one_after_first_page
    sync_repo(fake.client(), store, "o/r", NOW)
    assert store.count_issues() == 4
