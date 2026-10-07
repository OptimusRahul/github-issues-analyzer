"""Minimal GitHub REST client: pagination, rate-limit waits and the few writes triage needs."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Iterator

import httpx

API_URL = "https://api.github.com"
MAX_RATE_LIMIT_WAITS = 10
MAX_TRANSIENT_RETRIES = 3
TRANSIENT_STATUS = {502, 503, 504}


class GitHubError(Exception):
    """A GitHub API call failed."""


class RepoNotFound(GitHubError):
    """The repository or issue does not exist, or the token cannot see it."""


class RateLimitExceeded(GitHubError):
    """The rate limit resets later than the caller is willing to wait."""


@dataclass
class Page:
    items: list[dict]
    next_url: str | None


class GitHubClient:
    def __init__(
        self,
        token: str | None = None,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.time,
        max_wait: float = 3600.0,
    ):
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "issue-triage",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self.http = httpx.Client(
            base_url=API_URL, headers=headers, transport=transport, timeout=30.0, follow_redirects=True
        )
        self.sleep, self.clock, self.max_wait = sleep, clock, max_wait
        self._login: str | None = None

    def close(self) -> None:
        self.http.close()

    def _wait_seconds(self, response: httpx.Response) -> float | None:
        if response.status_code not in (403, 429):
            return None
        if "retry-after" in response.headers:
            return float(response.headers["retry-after"])
        if response.headers.get("x-ratelimit-remaining") == "0" and "x-ratelimit-reset" in response.headers:
            return max(0.0, float(response.headers["x-ratelimit-reset"]) - self.clock()) + 1.0
        return None

    def _send(self, method: str, url: str, **kwargs) -> httpx.Response:
        """One request, retried with backoff on network errors and 502/503/504."""
        for attempt in range(MAX_TRANSIENT_RETRIES + 1):
            try:
                response = self.http.request(method, url, **kwargs)
            except httpx.TransportError as e:
                if attempt == MAX_TRANSIENT_RETRIES:
                    raise GitHubError(f"Network error for {method} {url}: {e}") from e
            else:
                if response.status_code not in TRANSIENT_STATUS or attempt == MAX_TRANSIENT_RETRIES:
                    return response
            self.sleep(2.0**attempt)
        raise AssertionError("unreachable")

    def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        for _ in range(MAX_RATE_LIMIT_WAITS):
            response = self._send(method, url, **kwargs)
            wait = self._wait_seconds(response)
            if wait is None:
                break
            if wait > self.max_wait:
                raise RateLimitExceeded(
                    f"GitHub rate limit resets in {wait:.0f}s, longer than the {self.max_wait:.0f}s limit"
                )
            self.sleep(wait)
        else:
            raise RateLimitExceeded(f"Still rate limited after {MAX_RATE_LIMIT_WAITS} waits")
        if response.status_code == 404:
            raise RepoNotFound(f"Not found: {method} {url}")
        if response.status_code >= 400:
            raise GitHubError(f"GitHub returned {response.status_code} for {method} {url}: {response.text[:200]}")
        return response

    def viewer_login(self) -> str:
        """Login the token acts as. Actions' GITHUB_TOKEN cannot read /user and always posts as github-actions[bot]."""
        if self._login is None:
            try:
                self._login = self.request("GET", "/user").json()["login"].lower()
            except GitHubError:
                self._login = "github-actions[bot]"
        return self._login

    def resolve_repo(self, full_name: str) -> str:
        try:
            data = self.request("GET", f"/repos/{full_name}").json()
        except RepoNotFound:
            raise RepoNotFound(f"Repository {full_name} not found, or the token cannot read it") from None
        return data["full_name"].lower()

    def pages(self, path: str, params: dict | None = None, start_url: str | None = None) -> Iterator[Page]:
        url: str | None = start_url or path
        query = None if start_url else params
        while url:
            response = self.request("GET", url, params=query)
            next_url = response.links.get("next", {}).get("url")
            yield Page(response.json(), next_url)
            url, query = next_url, None

    def issue_comments(self, repo: str, number: int) -> list[dict]:
        return [c for page in self.pages(f"/repos/{repo}/issues/{number}/comments", {"per_page": 100}) for c in page.items]

    def create_comment(self, repo: str, number: int, body: str) -> dict:
        return self.request("POST", f"/repos/{repo}/issues/{number}/comments", json={"body": body}).json()

    def update_comment(self, repo: str, comment_id: int, body: str) -> dict:
        return self.request("PATCH", f"/repos/{repo}/issues/comments/{comment_id}", json={"body": body}).json()

    def add_labels(self, repo: str, number: int, labels: list[str]) -> None:
        self.request("POST", f"/repos/{repo}/issues/{number}/labels", json={"labels": labels})
