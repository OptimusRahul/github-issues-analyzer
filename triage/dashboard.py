"""Web dashboard served by the triage server: Jinja2 pages, htmx for search and Ask. Sign-in uses an API key."""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from triage.ask import AskError
from triage.commands import ignored_labels
from triage.digest import build_digest
from triage.dupes import find_candidates
from triage.labels import suggest_labels

COOKIE = "triage_session"
SESSION_SECONDS = 12 * 3600
RECENT_ISSUES = 10
CSP = (
    "default-src 'self'; script-src https://cdnjs.cloudflare.com; style-src 'self' 'unsafe-inline'; "
    "img-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
)

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


def register(app: FastAPI, core) -> None:
    """`core` holds the server's own functions (key check, rate limit, stores, API handlers)."""
    # ponytail: in-memory sessions; everyone signs in again after a restart. Store them if that annoys.
    sessions: dict[str, tuple[str, float]] = {}  # token -> (key hash, expiry)
    lock = threading.Lock()

    def signed_in(request: Request) -> str | None:
        token = request.cookies.get(COOKIE, "")
        with lock:
            digest, expires = sessions.get(token, ("", 0.0))
            if expires < time.time():
                sessions.pop(token, None)
                return None
        core.rate_limit(digest)
        return digest

    def page(request: Request, name: str, status: int = 200, **context) -> HTMLResponse:
        response = templates.TemplateResponse(request, name, {"logged_in": True, **context}, status_code=status)
        response.headers["Content-Security-Policy"] = CSP
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    def to_login() -> RedirectResponse:
        return RedirectResponse("/login", status_code=303)

    @app.get("/login", response_class=HTMLResponse, include_in_schema=False)
    def login_form(request: Request):
        return page(request, "login.html", logged_in=False)

    @app.post("/login", include_in_schema=False)
    def login(request: Request, key: str = Form(...)):
        digest = core.key_digest(key)
        if digest is None:
            return page(request, "login.html", 401, logged_in=False, error="That key is not valid.")
        core.rate_limit(digest)
        token = secrets.token_urlsafe(32)
        with lock:
            sessions[token] = (digest, time.time() + SESSION_SECONDS)
        response = RedirectResponse("/", status_code=303)
        response.set_cookie(
            COOKIE, token, max_age=SESSION_SECONDS, httponly=True, samesite="strict", secure=request.url.scheme == "https",
        )
        return response

    @app.post("/logout", include_in_schema=False)
    def logout(request: Request):
        with lock:
            sessions.pop(request.cookies.get(COOKIE, ""), None)
        response = RedirectResponse("/login", status_code=303)
        response.delete_cookie(COOKIE)
        return response

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def home(request: Request):
        if not signed_in(request):
            return to_login()
        return page(request, "index.html", repos=core.list_repos())

    @app.get("/r/{owner}/{name}", response_class=HTMLResponse, include_in_schema=False)
    def repo_page(request: Request, owner: str, name: str):
        if not signed_in(request):
            return to_login()
        repo = core.repo_of(owner, name)
        cfg, model = core.cfg, core.embedder.name
        now = datetime.now(timezone.utc)
        with core.open_store(repo) as store:
            digest = build_digest(store, model, cfg, now, None)
            index = store.matrix(model)
            known = set(int(n) for n in index[0])
            repo_labels = sorted({label for i in store.issues() for label in i["labels"]})
            open_issues = [i for i in store.issues() if i["state"] == "open" and i["number"] in known]
            recent = []
            for issue in sorted(open_issues, key=lambda i: i["created_at"], reverse=True)[:RECENT_ISSUES]:
                related = find_candidates(store, model, issue["number"], cfg.duplicates, cfg.exclude_labels, now, index)
                item = {**issue, "related": [asdict(c) for c in related], "labels": [], "priority": None}
                if cfg.labels.enabled:
                    s = suggest_labels(store, model, issue["number"], repo_labels, cfg.labels, now, None, ignored_labels(cfg), index)
                    item.update(labels=s.labels, priority=s.priority)
                recent.append(item)
            context = {
                "repo": repo,
                "url_base": f"https://github.com/{repo}",
                "issues": store.count_issues(),
                "last_synced_at": store.get_state("last_synced_at"),
                "window_days": digest.window_days,
                "themes": digest.new_themes + digest.growing_themes,
                "recent": recent,
            }
        return page(request, "repo.html", **context)

    @app.get("/r/{owner}/{name}/search", response_class=HTMLResponse, include_in_schema=False)
    def search_partial(request: Request, owner: str, name: str, q: str = ""):
        if not signed_in(request):
            return page(request, "_hits.html", error="Your session ended. Reload the page to sign in again.")
        if not q.strip():
            return page(request, "_hits.html", hits=[])
        return page(request, "_hits.html", hits=core.search(owner, name, q.strip()))

    @app.post("/r/{owner}/{name}/ask", response_class=HTMLResponse, include_in_schema=False)
    def ask_partial(request: Request, owner: str, name: str, question: str = Form("")):
        if not signed_in(request):
            return page(request, "_answer.html", error="Your session ended. Reload the page to sign in again.")
        from triage.server import AskQuestion

        try:
            result = core.ask(owner, name, AskQuestion(question=question))
        except (AskError, HTTPException) as e:
            # htmx swaps only 2xx responses by default, so errors come back as 200 with a message.
            return page(request, "_answer.html", error=getattr(e, "detail", None) or str(e))
        return page(request, "_answer.html", answer=result["answer"], citations=result["citations"])
