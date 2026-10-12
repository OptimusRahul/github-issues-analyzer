import hashlib
import hmac
import json
import logging

import pytest
from fastapi.testclient import TestClient

from tests.triage.helpers import FakeClient, FakeGitHub, WordHashEmbedder, gh_issue
from triage.config import Config, DuplicatesConfig, LLMConfig
from triage.llm import ChatModel
from triage.server import ServerSettings, create_app

KEY = "s3cret-key"
SECRET = "hook-secret"
ISSUES = [
    gh_issue(1, "App crashes when opening settings on Windows"),
    gh_issue(2, "Crash when opening settings on Windows 11"),
    gh_issue(3, "Add dark theme to editor"),
]


def settings(tmp_path, **overrides):
    values = dict(
        repos=["o/r"],
        api_key_hashes=[hashlib.sha256(KEY.encode()).hexdigest()],
        webhook_secret=SECRET,
        index_dir=tmp_path,
        rate_per_minute=100,
        ask_calls_per_day=10,
        cors_origins=["https://dash.example"],
        sync_minutes=0,
    )
    values.update(overrides)
    return ServerSettings(**values)


@pytest.fixture
def server(tmp_path):
    def make(cfg=None, replies=(), embedder=None, **overrides):
        fake = FakeGitHub(issues=ISSUES)
        replies = list(replies)
        app = create_app(
            settings(tmp_path, **overrides),
            cfg or Config(duplicates=DuplicatesConfig(threshold=0.5)),
            github=fake.client,
            embedder=embedder or WordHashEmbedder(),
            chat=lambda task, max_calls, cls=ChatModel: cls(LLMConfig(base_url="http://x", model="m"), client=FakeClient(*replies), max_calls=max_calls, task=task),
        )
        client = TestClient(app, raise_server_exceptions=False)
        client.headers["Authorization"] = f"Bearer {KEY}"
        client.post("/api/repos/o/r/sync")
        return client, fake

    return make


def sign(body: bytes, secret=SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_health_needs_no_key(server):
    client, _ = server()
    assert client.get("/health", headers={"Authorization": ""}).json() == {"status": "ok"}


def test_api_rejects_missing_or_wrong_key(server):
    client, _ = server()
    assert client.get("/api/repos", headers={"Authorization": ""}).status_code == 401
    assert client.get("/api/repos", headers={"Authorization": "Bearer nope"}).status_code == 401
    repos = client.get("/api/repos").json()
    assert repos[0]["repo"] == "o/r" and repos[0]["issues"] == 3 and repos[0]["last_synced_at"]


def test_rate_limit_returns_429_with_retry_after(server):
    client, _ = server(rate_per_minute=3)  # the fixture's sync uses one
    assert client.get("/api/repos").status_code == 200
    assert client.get("/api/repos").status_code == 200
    response = client.get("/api/repos")
    assert response.status_code == 429 and int(response.headers["Retry-After"]) >= 1


def test_unknown_repo_is_404(server):
    client, _ = server()
    assert client.get("/api/repos/x/y/search", params={"q": "crash"}).status_code == 404


def test_search_returns_hits(server):
    client, _ = server()
    hits = client.get("/api/repos/o/r/search", params={"q": "settings crash"}).json()
    assert {h["number"] for h in hits[:2]} == {1, 2}


def test_ask_answers_with_citations_and_respects_daily_budget(server):
    reply = json.dumps({"answer": "Settings crash on Windows [#1].", "citations": [1, 99]})
    client, _ = server(replies=[reply], ask_calls_per_day=1)
    body = client.post("/api/repos/o/r/ask", json={"question": "Why does it crash?"}).json()
    assert [c["number"] for c in body["citations"]] == [1]
    response = client.post("/api/repos/o/r/ask", json={"question": "Again?"})
    assert response.status_code == 429


def test_bad_question_is_400(server):
    client, _ = server()
    assert client.post("/api/repos/o/r/ask", json={"question": ""}).status_code == 400


def test_related_issues_endpoint(server):
    client, _ = server()
    body = client.get("/api/repos/o/r/issues/2/related").json()
    assert [c["number"] for c in body["related"]] == [1]
    assert client.get("/api/repos/o/r/issues/999/related").status_code == 404


def test_digest_endpoint_returns_markdown_without_posting(server):
    client, fake = server(cfg=Config(dry_run=False))
    assert client.get("/api/repos/o/r/digest").json()["markdown"].startswith("#")
    assert fake.created_issues == []


def test_webhook_rejects_bad_signature_and_missing_secret(server, tmp_path):
    client, _ = server()
    body = json.dumps({"action": "opened", "issue": {"number": 2}, "repository": {"full_name": "o/r"}}).encode()
    headers = {"X-GitHub-Event": "issues", "X-Hub-Signature-256": sign(body, "wrong")}
    assert client.post("/webhook", content=body, headers=headers).status_code == 401
    client, _ = server(webhook_secret=None)
    headers["X-Hub-Signature-256"] = sign(body)
    assert client.post("/webhook", content=body, headers=headers).status_code == 503


def test_webhook_checks_new_issue(server):
    cfg = Config(dry_run=False, duplicates=DuplicatesConfig(threshold=0.5))
    client, fake = server(cfg=cfg, replies=['{"duplicates": []}'])
    body = json.dumps({"action": "opened", "issue": {"number": 2}, "repository": {"full_name": "O/R"}}).encode()
    response = client.post("/webhook", content=body, headers={"X-GitHub-Event": "issues", "X-Hub-Signature-256": sign(body)})
    assert response.status_code == 202
    assert "Related issues" in fake.issue_comments[2][0]["body"]


def test_webhook_ignores_other_events_and_repos(server):
    client, fake = server()
    for event, payload in [("ping", {"zen": "hi"}), ("issues", {"action": "opened", "issue": {"number": 2}, "repository": {"full_name": "x/y"}})]:
        body = json.dumps(payload).encode()
        assert client.post("/webhook", content=body, headers={"X-GitHub-Event": event, "X-Hub-Signature-256": sign(body)}).status_code == 200
    assert fake.issue_comments == {}


class ExplodingEmbedder(WordHashEmbedder):
    def embed(self, texts):
        if texts == ["boom"]:
            raise RuntimeError("database password is hunter2")
        return super().embed(texts)


def test_500_hides_exception_text_and_returns_request_id(server, caplog):
    client, _ = server(embedder=ExplodingEmbedder())
    with caplog.at_level(logging.ERROR, logger="triage.server"):
        response = client.get("/api/repos/o/r/search", params={"q": "boom"})
    assert response.status_code == 500
    assert "hunter2" not in response.text
    request_id = response.json()["request_id"]
    assert response.headers["X-Request-ID"] == request_id
    assert any(request_id in r.getMessage() for r in caplog.records)


def test_info_logs_contain_no_issue_text_or_questions(server, caplog):
    reply = json.dumps({"answer": "See [#1].", "citations": [1]})
    client, _ = server(replies=[reply])
    with caplog.at_level(logging.INFO, logger="triage"):
        client.post("/api/repos/o/r/ask", json={"question": "Why does settings crash?"})
    text = "\n".join(r.getMessage() for r in caplog.records)
    assert "settings" not in text.lower() and "Why does" not in text


def test_cors_allows_only_configured_origins(server):
    client, _ = server()
    ok = client.get("/health", headers={"Origin": "https://dash.example"})
    bad = client.get("/health", headers={"Origin": "https://evil.example"})
    assert ok.headers.get("access-control-allow-origin") == "https://dash.example"
    assert "access-control-allow-origin" not in bad.headers


def test_settings_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("TRIAGE_REPOS", "o/r, a/b")
    monkeypatch.setenv("TRIAGE_API_KEYS", "abc,def")
    monkeypatch.delenv("TRIAGE_CORS_ORIGINS", raising=False)
    s = ServerSettings.from_env()
    assert s.repos == ["o/r", "a/b"] and s.api_key_hashes == ["abc", "def"] and s.cors_origins == []
