import json

import httpx
import pytest

from triage.github import GitHubClient, GitHubError, RateLimitExceeded, RepoNotFound


def make_client(handler, **kwargs):
    return GitHubClient(token="t", transport=httpx.MockTransport(handler), **kwargs)


def test_pages_follow_link_header_and_send_params_once():
    seen = []

    def handler(request):
        seen.append(request.url)
        if request.url.params.get("page") == "2":
            return httpx.Response(200, json=[{"n": 2}])
        return httpx.Response(
            200, json=[{"n": 1}], headers={"link": '<https://api.github.com/repos/o/r/issues?per_page=100&page=2>; rel="next"'}
        )

    pages = list(make_client(handler).pages("/repos/o/r/issues", {"per_page": 100}))
    assert [p.items for p in pages] == [[{"n": 1}], [{"n": 2}]]
    assert pages[0].next_url.endswith("page=2")
    assert pages[1].next_url is None
    assert seen[0].params["per_page"] == "100"


def test_pages_resume_from_start_url():
    seen = []

    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(200, json=[])

    start = "https://api.github.com/repos/o/r/issues?per_page=100&page=7"
    list(make_client(handler).pages("/repos/o/r/issues", {"per_page": 100}, start_url=start))
    assert seen == [start]


def test_waits_for_rate_limit_reset_then_retries():
    calls, sleeps = [], []

    def handler(request):
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(403, headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": "1030"})
        return httpx.Response(200, json={"ok": True})

    client = make_client(handler, sleep=sleeps.append, clock=lambda: 1000.0)
    assert client.request("GET", "/rate").json() == {"ok": True}
    assert sleeps == [31.0]


def test_honours_retry_after_on_secondary_limit():
    sleeps = []
    responses = [httpx.Response(429, headers={"retry-after": "5"}), httpx.Response(200, json={})]
    client = make_client(lambda request: responses.pop(0), sleep=sleeps.append)
    client.request("GET", "/x")
    assert sleeps == [5.0]


def test_rate_limit_longer_than_max_wait_raises():
    def handler(request):
        return httpx.Response(403, headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": "9000"})

    client = make_client(handler, sleep=lambda s: None, clock=lambda: 1000.0, max_wait=3600)
    with pytest.raises(RateLimitExceeded):
        client.request("GET", "/x")


def test_403_without_rate_limit_headers_is_an_error():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(403, json={"message": "Resource not accessible by integration"})

    with pytest.raises(GitHubError, match="403") as info:
        make_client(handler, sleep=lambda s: pytest.fail("must not wait")).request("GET", "/x")
    assert not isinstance(info.value, RateLimitExceeded)
    assert len(calls) == 1


def test_resolve_repo_follows_rename_and_lowercases():
    def handler(request):
        if request.url.path == "/repos/Old/Name":
            return httpx.Response(301, headers={"location": "https://api.github.com/repositories/42"})
        return httpx.Response(200, json={"full_name": "New/Name"})

    assert make_client(handler).resolve_repo("Old/Name") == "new/name"


def test_resolve_repo_private_or_missing_is_not_found():
    client = make_client(lambda request: httpx.Response(404, json={"message": "Not Found"}))
    with pytest.raises(RepoNotFound, match="o/secret not found"):
        client.resolve_repo("o/secret")


def test_comment_and_label_writes():
    seen = []

    def handler(request):
        seen.append((request.method, request.url.path, request.content))
        return httpx.Response(200, json={"id": 5})

    client = make_client(handler)
    client.create_comment("o/r", 3, "hi")
    client.update_comment("o/r", 5, "edit")
    client.add_labels("o/r", 3, ["possible-duplicate"])
    assert [(m, p) for m, p, _ in seen] == [
        ("POST", "/repos/o/r/issues/3/comments"),
        ("PATCH", "/repos/o/r/issues/comments/5"),
        ("POST", "/repos/o/r/issues/3/labels"),
    ]


def test_retries_network_errors_with_backoff_then_succeeds():
    calls, sleeps = [], []

    def handler(request):
        calls.append(1)
        if len(calls) < 3:
            raise httpx.ReadTimeout("slow", request=request)
        return httpx.Response(200, json={"ok": True})

    assert make_client(handler, sleep=sleeps.append).request("GET", "/x").json() == {"ok": True}
    assert sleeps == [1.0, 2.0]


def test_persistent_network_error_becomes_a_github_error():
    def handler(request):
        raise httpx.ConnectError("down", request=request)

    with pytest.raises(GitHubError, match="Network error"):
        make_client(handler, sleep=lambda s: None).request("GET", "/x")


def test_retries_bad_gateway():
    sleeps = []
    responses = [httpx.Response(502), httpx.Response(200, json={})]
    make_client(lambda request: responses.pop(0), sleep=sleeps.append).request("GET", "/x")
    assert sleeps == [1.0]


def test_viewer_login_is_unknown_when_token_cannot_read_user():
    client = make_client(lambda request: httpx.Response(403, json={"message": "Resource not accessible by integration"}))
    assert client.viewer_login() is None


def test_viewer_login_does_not_hide_other_errors():
    def handler(request):
        raise httpx.ConnectError("down", request=request)

    with pytest.raises(GitHubError, match="Network error"):
        make_client(handler, sleep=lambda s: None).viewer_login()


def test_writes_are_not_retried_after_bad_gateway():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(502)

    with pytest.raises(GitHubError, match="502"):
        make_client(handler, sleep=lambda s: pytest.fail("must not retry a write")).create_comment("o/r", 1, "hi")
    assert len(calls) == 1


def test_writes_are_not_retried_after_network_error():
    calls = []

    def handler(request):
        calls.append(1)
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(GitHubError, match="Network error"):
        make_client(handler, sleep=lambda s: pytest.fail("must not retry a write")).update_comment("o/r", 5, "x")
    assert len(calls) == 1


def test_create_issue_posts_title_and_body():
    seen = []

    def handler(request):
        seen.append((request.method, request.url.path, json.loads(request.content)))
        return httpx.Response(201, json={"number": 7, "html_url": "https://github.com/o/r/issues/7"})

    assert make_client(handler).create_issue("o/r", "Digest", "body")["number"] == 7
    assert seen == [("POST", "/repos/o/r/issues", {"title": "Digest", "body": "body"})]
