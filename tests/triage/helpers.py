"""Shared test helpers: GitHub-shaped fixtures, a fake GitHub API and a deterministic embedder."""

from __future__ import annotations

import json
import re
import zlib

import httpx
import numpy as np


def gh_issue(
    number,
    title="Issue",
    body="",
    state="open",
    created="2026-01-01T00:00:00Z",
    updated=None,
    closed=None,
    labels=(),
    state_reason=None,
    pr=False,
    reactions=0,
    assignees=(),
    milestone=None,
    author="someone",
):
    item = {
        "number": number,
        "title": title,
        "body": body,
        "state": state,
        "state_reason": state_reason,
        "labels": [{"name": name} for name in labels],
        "author_association": "NONE",
        "comments": 0,
        "reactions": {"total_count": reactions},
        "html_url": f"https://github.com/o/r/issues/{number}",
        "created_at": created,
        "updated_at": updated or created,
        "closed_at": closed,
        "assignees": [{"login": login} for login in assignees],
        "milestone": {"title": milestone} if milestone else None,
        "user": {"login": author},
    }
    if pr:
        item["pull_request"] = {"url": f"https://api.github.com/repos/o/r/pulls/{number}"}
    return item


def gh_comment(comment_id, issue_number, body, created="2026-01-02T00:00:00Z", association="NONE"):
    return {
        "id": comment_id,
        "issue_url": f"https://api.github.com/repos/o/r/issues/{issue_number}",
        "body": body,
        "author_association": association,
        "created_at": created,
        "updated_at": created,
    }


class WordHashEmbedder:
    """Deterministic bag-of-words embedder: texts that share words get similar vectors."""

    name = "test:word-hash"

    def __init__(self):
        self.calls = 0

    def usage_summary(self):
        return ""

    def embed(self, texts):
        self.calls += 1
        out = np.zeros((len(texts), 256), dtype=np.float32)
        for i, text in enumerate(texts):
            for word in re.findall(r"[a-z0-9]+", text.lower()):
                out[i, zlib.crc32(word.encode()) % 256] += 1.0
        return out


class FakeGitHub:
    """In-memory GitHub API for one repo. Serves paginated issues and comments, records requests."""

    def __init__(self, issues=(), comments=(), per_page=100, repo="o/r"):
        self.repo = repo
        self.issues = list(issues)
        self.comments = list(comments)
        self.per_page = per_page
        self.requests: list[httpx.Request] = []
        self.fail_once: set[str] = set()
        self.issue_comments: dict[int, list[dict]] = {}
        self.labels: dict[int, list[str]] = {}
        self.login = "triage-bot"
        self.user_forbidden = False  # True mimics GitHub App / Actions tokens, which cannot read /user
        self.on_request = None
        self._next_id = 1000

    def client(self):
        from triage.github import GitHubClient

        return GitHubClient(token="t", transport=httpx.MockTransport(self.handler), sleep=lambda s: None)

    def _page(self, request, kind, items):
        page = int(request.url.params.get("page", "1"))
        key = f"{kind}:{page}"
        if key in self.fail_once:
            self.fail_once.discard(key)
            return httpx.Response(500, json={"message": "boom"})
        sort_key = {"updated": "updated_at", "created": "created_at"}.get(request.url.params.get("sort"))
        if sort_key:
            items = sorted(items, key=lambda item: item[sort_key])
        chunk = items[(page - 1) * self.per_page : page * self.per_page]
        headers = {}
        if page * self.per_page < len(items):
            next_url = request.url.copy_merge_params({"page": page + 1})
            headers["link"] = f'<{next_url}>; rel="next"'
        return httpx.Response(200, json=chunk, headers=headers)

    def handler(self, request):
        self.requests.append(request)
        response = self._route(request)
        if self.on_request:
            self.on_request(request)
        return response

    def _route(self, request):
        path, method = request.url.path, request.method
        base = f"/repos/{self.repo}"
        if path == "/user":
            if self.user_forbidden:
                return httpx.Response(403, json={"message": "Resource not accessible by integration"})
            return httpx.Response(200, json={"login": self.login})
        if path == base:
            return httpx.Response(200, json={"full_name": self.repo})
        if method == "GET" and path == f"{base}/issues":
            return self._page(request, "issues", self.issues)
        if method == "GET" and path == f"{base}/issues/comments":
            return self._page(request, "comments", self.comments)
        match = re.fullmatch(rf"{base}/issues/(\d+)/comments", path)
        if match:
            number = int(match.group(1))
            if method == "GET":
                return httpx.Response(200, json=self.issue_comments.get(number, []))
            self._next_id += 1
            comment = {"id": self._next_id, "body": json.loads(request.content)["body"], "user": {"login": self.login, "type": "Bot" if self.user_forbidden else "User"}}
            self.issue_comments.setdefault(number, []).append(comment)
            return httpx.Response(201, json=comment)
        match = re.fullmatch(rf"{base}/issues/comments/(\d+)", path)
        if match and method == "PATCH":
            comment_id = int(match.group(1))
            for comments in self.issue_comments.values():
                for comment in comments:
                    if comment["id"] == comment_id:
                        comment["body"] = json.loads(request.content)["body"]
                        return httpx.Response(200, json=comment)
        match = re.fullmatch(rf"{base}/issues/(\d+)/labels", path)
        if match and method == "POST":
            labels = json.loads(request.content)["labels"]
            self.labels.setdefault(int(match.group(1)), []).extend(labels)
            return httpx.Response(200, json=[{"name": name} for name in labels])
        return httpx.Response(404, json={"message": "Not Found"})
