"""HTTP server on the triage engine: webhook for new issues, scheduled sync and digest, search, Ask and a
dashboard. Same config file and index files as the CLI. Needs the `server` extra."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import math
import os
import threading
import time
import uuid
from contextlib import asynccontextmanager, contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Callable

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from triage.ask import AskError, ask
from triage.cli import index_path
from triage.commands import check_duplicates, check_labels, ignored_labels, run_digest
from triage.config import Config, ConfigError, load_config
from triage.digest import build_digest, render_digest
from triage.dupes import NotInIndex, find_candidates
from triage.embed import Embedder, SetupError, embed_pending, make_embedder
from triage.github import GitHubClient, GitHubError
from triage.labels import suggest_labels
from triage.llm import ChatModel, Confirmer
from triage.search import hybrid_search
from triage.store import Store
from triage.sync import IndexMismatch, sync_repo

log = logging.getLogger("triage.server")


def _split(value: str | None) -> list[str]:
    return [part.strip() for part in (value or "").split(",") if part.strip()]


@dataclass
class ServerSettings:
    repos: list[str]
    api_key_hashes: list[str] = field(default_factory=list)  # sha256 hex of each API key
    webhook_secret: str | None = None
    index_dir: Path = Path(".triage")
    rate_per_minute: int = 60  # API requests per key
    ask_calls_per_day: int = 200  # LLM calls for Ask, all keys together
    cors_origins: list[str] = field(default_factory=list)
    sync_minutes: int = 60  # 0 turns the scheduler off

    @classmethod
    def from_env(cls) -> ServerSettings:
        env = os.environ.get
        return cls(
            repos=_split(env("TRIAGE_REPOS")),
            api_key_hashes=[h.lower() for h in _split(env("TRIAGE_API_KEYS"))],
            webhook_secret=env("TRIAGE_WEBHOOK_SECRET") or None,
            index_dir=Path(env("TRIAGE_INDEX_DIR", ".triage")),
            rate_per_minute=int(env("TRIAGE_RATE_PER_MINUTE", "60")),
            ask_calls_per_day=int(env("TRIAGE_ASK_CALLS_PER_DAY", "200")),
            cors_origins=_split(env("TRIAGE_CORS_ORIGINS")),
            sync_minutes=int(env("TRIAGE_SYNC_MINUTES", "60")),
        )


class RateLimiter:
    """Token bucket per API key. In memory: limits reset when the server restarts."""

    def __init__(self, per_minute: int, clock: Callable[[], float] = time.monotonic):
        self.capacity = per_minute
        self.clock = clock
        self.buckets: dict[str, tuple[float, float]] = {}  # key -> (tokens, last refill)
        self.lock = threading.Lock()

    def retry_after(self, key: str) -> int:
        """0 if the request may go ahead (and is counted), otherwise seconds until it may."""
        with self.lock:
            now = self.clock()
            tokens, last = self.buckets.get(key, (self.capacity, now))
            tokens = min(self.capacity, tokens + (now - last) * self.capacity / 60)
            if tokens >= 1:
                self.buckets[key] = (tokens - 1, now)
                return 0
            self.buckets[key] = (tokens, now)
            return math.ceil((1 - tokens) * 60 / self.capacity)


class AskQuestion(BaseModel):
    question: str


def create_app(
    settings: ServerSettings,
    cfg: Config,
    github: Callable[[], GitHubClient],
    embedder: Embedder,
    chat: Callable[..., ChatModel | None] | None = None,
) -> FastAPI:
    """`chat(task, max_calls, cls=ChatModel)` builds the model for a task, or None if none is configured."""
    repos = {r.lower() for r in settings.repos}
    locks = {r: threading.Lock() for r in repos}  # one writer per index file
    limiter = RateLimiter(settings.rate_per_minute)
    ask_usage = {"day": "", "calls": 0}
    ask_lock = threading.Lock()

    def default_chat(task: str, max_calls: int, cls=ChatModel):
        llm = cfg.models.llm_for(task)
        return cls(llm, max_calls=max_calls, task=task) if llm.enabled else None

    make_chat = chat or default_chat

    @contextmanager
    def open_store(repo: str):
        store = Store(index_path(settings.index_dir, repo))
        try:
            yield store
        finally:
            store.close()

    def refresh(repo: str) -> None:
        with locks[repo], open_store(repo) as store:
            gh = github()
            try:
                sync_repo(gh, store, repo, datetime.now(timezone.utc), cfg.comments_window_days)
                embed_pending(store, embedder)
            finally:
                gh.close()

    def check_issue(repo: str, number: int) -> None:
        now = datetime.now(timezone.utc)
        limit = cfg.limits.max_llm_calls_per_run
        with locks[repo], open_store(repo) as store:
            gh = github()
            try:
                confirmer = make_chat("confirm", limit, Confirmer)
                dupes = check_duplicates(gh, store, embedder, cfg, repo, number, now, confirmer)
                labels = check_labels(gh, store, embedder, cfg, repo, number, now, make_chat("labels", limit))
                log.info("checked %s#%d: duplicates %s, labels %s", repo, number, dupes.action, labels.action)
            except Exception:
                log.exception("checking %s#%d failed", repo, number)
            finally:
                gh.close()

    def digest_if_due(repo: str) -> None:
        now = datetime.now(timezone.utc)
        with locks[repo], open_store(repo) as store:
            last = store.get_state("last_digest_at")
            if last and datetime.fromisoformat(last) > now - timedelta(days=cfg.digest.window_days):
                return
            gh = github()
            try:
                namer = make_chat("themes", cfg.limits.max_llm_calls_per_run)
                outcome = run_digest(gh, store, embedder, cfg, repo, now, namer)
                store.set_state("last_digest_at", now.isoformat())
                store.commit()
                log.info("digest for %s: %s", repo, outcome.action)
            finally:
                gh.close()

    def scheduler(stop: threading.Event) -> None:
        while not stop.is_set():
            for repo in sorted(repos):
                try:
                    refresh(repo)
                    digest_if_due(repo)
                except Exception:
                    log.exception("scheduled run for %s failed", repo)
            stop.wait(settings.sync_minutes * 60)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        stop = threading.Event()
        if settings.sync_minutes > 0:
            threading.Thread(target=scheduler, args=(stop,), daemon=True, name="triage-scheduler").start()
        yield
        stop.set()

    app = FastAPI(title="issue-triage", lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.middleware("http")
    async def request_id(request: Request, call_next):
        rid = uuid.uuid4().hex[:12]
        request.state.request_id = rid
        started = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            log.exception("request %s failed", rid)
            response = JSONResponse({"detail": "Internal error", "request_id": rid}, status_code=500)
        response.headers["X-Request-ID"] = rid
        # Path only: query strings can hold search text. Never log bodies.
        log.info("%s %s %d %dms id=%s", request.method, request.url.path, response.status_code, (time.monotonic() - started) * 1000, rid)
        return response

    def error(status: int, detail: str):
        async def handler(request: Request, exc: Exception):
            return JSONResponse({"detail": detail or str(exc), "request_id": request.state.request_id}, status_code=status)
        return handler

    app.add_exception_handler(NotInIndex, error(404, ""))
    app.add_exception_handler(AskError, error(400, ""))
    app.add_exception_handler(ConfigError, error(400, ""))
    app.add_exception_handler(IndexMismatch, error(409, "The index file belongs to another repository"))
    app.add_exception_handler(GitHubError, error(502, "A GitHub request failed"))
    app.add_exception_handler(SetupError, error(500, "The server is missing an optional dependency"))

    def key_digest(key: str) -> str | None:
        """The configured hash of `key`, or None if it is not a valid API key."""
        digest = hashlib.sha256(key.encode()).hexdigest()
        known = any(hmac.compare_digest(digest, h) for h in settings.api_key_hashes)
        return digest if key and known else None

    def rate_limit(digest: str) -> None:
        if wait := limiter.retry_after(digest):
            raise HTTPException(429, "Rate limit exceeded", headers={"Retry-After": str(wait)})

    def authorize(request: Request) -> str:
        scheme, _, key = request.headers.get("Authorization", "").partition(" ")
        digest = key_digest(key) if scheme.lower() == "bearer" else None
        if digest is None:
            raise HTTPException(401, "Missing or invalid API key", headers={"WWW-Authenticate": "Bearer"})
        rate_limit(digest)
        return digest

    def repo_of(owner: str, name: str) -> str:
        repo = f"{owner}/{name}".lower()
        if repo not in repos:
            raise HTTPException(404, "Unknown repository")
        return repo

    api = Depends(authorize)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/repos", dependencies=[api])
    def list_repos():
        out = []
        for repo in sorted(repos):
            with open_store(repo) as store:
                out.append({"repo": repo, "issues": store.count_issues(), "last_synced_at": store.get_state("last_synced_at")})
        return out

    @app.post("/api/repos/{owner}/{name}/sync", dependencies=[api], status_code=202)
    def sync_now(owner: str, name: str, tasks: BackgroundTasks):
        tasks.add_task(refresh, repo_of(owner, name))
        return {"status": "queued"}

    @app.get("/api/repos/{owner}/{name}/search", dependencies=[api])
    def search(owner: str, name: str, q: str, state: str | None = None, label: list[str] | None = None, since: str | None = None, limit: int = 10):
        with open_store(repo_of(owner, name)) as store:
            hits = hybrid_search(store, embedder, q, min(max(limit, 1), 50), state, label, since)
        return [asdict(h) for h in hits]

    @app.post("/api/repos/{owner}/{name}/ask", dependencies=[api])
    def ask_question(owner: str, name: str, body: AskQuestion):
        repo = repo_of(owner, name)
        today = datetime.now(timezone.utc).date().isoformat()
        with ask_lock:
            if ask_usage["day"] != today:
                ask_usage.update(day=today, calls=0)
            remaining = settings.ask_calls_per_day - ask_usage["calls"]
        if remaining <= 0:
            raise HTTPException(429, "Daily Ask budget spent", headers={"Retry-After": "3600"})
        model = make_chat("ask", remaining)
        if model is None:
            raise HTTPException(400, "No model configured for Ask (models.ask or models.llm)")
        try:
            with open_store(repo) as store:
                answer = ask(store, embedder, model, body.question)
        finally:
            with ask_lock:
                ask_usage["calls"] += model.calls
        return {"answer": answer.text, "citations": [asdict(h) for h in answer.citations]}

    @app.get("/api/repos/{owner}/{name}/issues/{number}/related", dependencies=[api])
    def related(owner: str, name: str, number: int):
        """Related issues and label suggestions, computed without posting anything or calling an LLM."""
        repo = repo_of(owner, name)
        now = datetime.now(timezone.utc)
        with open_store(repo) as store:
            index = store.matrix(embedder.name)
            found = find_candidates(store, embedder.name, number, cfg.duplicates, cfg.exclude_labels, now, index)
            result = {"related": [asdict(c) for c in found]}
            if cfg.labels.enabled:
                labels = [label for label in {lab for i in store.issues() for lab in i["labels"]}]
                s = suggest_labels(store, embedder.name, number, sorted(labels), cfg.labels, now, None, ignored_labels(cfg), index)
                result["labels"] = asdict(s)
        return result

    @app.get("/api/repos/{owner}/{name}/digest", dependencies=[api])
    def digest(owner: str, name: str):
        """The digest as it would be posted now, from the current index. Posts nothing."""
        repo = repo_of(owner, name)
        now = datetime.now(timezone.utc)
        with open_store(repo) as store:
            body = render_digest(repo, build_digest(store, embedder.name, cfg, now, None), now)
        return {"markdown": body}

    @app.post("/webhook")
    async def webhook(request: Request, tasks: BackgroundTasks):
        if not settings.webhook_secret:
            raise HTTPException(503, "Webhook secret is not configured (TRIAGE_WEBHOOK_SECRET)")
        body = await request.body()
        expected = "sha256=" + hmac.new(settings.webhook_secret.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, request.headers.get("X-Hub-Signature-256", "")):
            raise HTTPException(401, "Invalid signature")
        payload = json.loads(body or b"{}")
        repo = ((payload.get("repository") or {}).get("full_name") or "").lower()
        if request.headers.get("X-GitHub-Event") != "issues" or payload.get("action") != "opened" or repo not in repos:
            return {"status": "ignored"}
        number = int(payload["issue"]["number"])
        tasks.add_task(check_issue, repo, number)
        return JSONResponse({"status": "queued"}, status_code=202)

    from triage.dashboard import register

    register(app, SimpleNamespace(
        key_digest=key_digest, rate_limit=rate_limit, repo_of=repo_of, open_store=open_store, embedder=embedder, cfg=cfg,
        list_repos=list_repos, search=search, ask=ask_question, related=related,
    ))
    return app


def app_from_env() -> FastAPI:
    """The app as `triage serve` runs it: settings from TRIAGE_* variables, models from the config file."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = ServerSettings.from_env()
    if not settings.repos:
        raise ConfigError("TRIAGE_REPOS: set it to one or more owner/repo, separated by commas")
    if not settings.api_key_hashes:
        log.warning("TRIAGE_API_KEYS is empty: every /api request will be refused")
    cfg = load_config(Path(os.environ.get("TRIAGE_CONFIG", ".github/issue-triage.yml")))
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    return create_app(settings, cfg, github=lambda: GitHubClient(token=token), embedder=make_embedder(cfg.models.embeddings))
