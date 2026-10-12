from tests.triage.helpers import FakeGitHub
from triage.comment import MARKER, post_or_update, render_comment
from triage.dupes import Candidate


def test_render_splits_confirmed_duplicates_from_related_issues():
    body = render_comment([Candidate(3, "Settings crash", "u", "open", 0.9, "Same crash", confirmed=True), Candidate(1, "Crash", "u", "closed", 0.8)])
    assert body.startswith(MARKER)
    duplicates, related = body.split("Related issues")
    assert "may be a duplicate of" in duplicates and "- #3 Settings crash (Same crash)" in duplicates
    assert "- #1 Crash" in related
    assert "never closes issues" in body


def test_render_without_confirmed_duplicates_lists_related_only():
    body = render_comment([Candidate(1, "Crash", "u", "closed", 0.8)])
    assert "duplicate of" not in body and "Related issues" in body and "- #1 Crash" in body


def test_render_neutralises_mentions_and_html_in_titles():
    body = render_comment([Candidate(3, "Ping @octocat <img src=x onerror=alert(1)>", "u", "open", 0.9)])
    assert "@octocat" not in body
    assert "<img" not in body


def test_post_creates_then_updates_existing_comment_and_adds_label():
    fake = FakeGitHub()
    gh = fake.client()
    assert post_or_update(gh, "o/r", 7, f"{MARKER}\nfirst", ["possible-duplicate"]) == "created"
    assert post_or_update(gh, "o/r", 7, f"{MARKER}\nsecond", []) == "updated"
    assert [c["body"] for c in fake.issue_comments[7]] == [f"{MARKER}\nsecond"]
    assert fake.labels[7] == ["possible-duplicate"]


def test_post_ignores_other_peoples_comments():
    fake = FakeGitHub()
    fake.issue_comments[7] = [{"id": 1, "body": "I have this too"}]
    assert post_or_update(fake.client(), "o/r", 7, f"{MARKER}\nx", []) == "created"
    assert len(fake.issue_comments[7]) == 2


def test_post_never_edits_another_users_comment_that_contains_the_marker():
    fake = FakeGitHub()
    fake.issue_comments[7] = [{"id": 1, "body": f"{MARKER}\nspoofed", "user": {"login": "mallory"}}]
    assert post_or_update(fake.client(), "o/r", 7, f"{MARKER}\nreal", []) == "created"
    assert fake.issue_comments[7][0]["body"] == f"{MARKER}\nspoofed"
    assert len(fake.issue_comments[7]) == 2


def test_app_token_updates_its_own_bot_comment_but_not_a_humans():
    fake = FakeGitHub()
    fake.user_forbidden = True
    fake.issue_comments[7] = [
        {"id": 1, "body": f"{MARKER}\nspoofed", "user": {"login": "mallory", "type": "User"}},
        {"id": 2, "body": f"{MARKER}\nold", "user": {"login": "my-app[bot]", "type": "Bot"}},
    ]
    assert post_or_update(fake.client(), "o/r", 7, f"{MARKER}\nnew", []) == "updated"
    assert [c["body"] for c in fake.issue_comments[7]] == [f"{MARKER}\nspoofed", f"{MARKER}\nnew"]
