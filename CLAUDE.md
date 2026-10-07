# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Uses [uv](https://github.com/astral-sh/uv). Python >= 3.10.

```bash
uv sync                      # install deps (incl. dev: pytest, pytest-asyncio, httpx)
cp .env.example .env         # then set OPENAI_API_KEY (required), GITHUB_TOKEN (optional)
uv run main.py               # dev server on :8000 with reload; docs at /docs
uvx ruff check triage tests  # lint (what CI runs); ruff is not in uv dev deps (config in pyproject)
uv run pytest tests/triage                         # triage engine tests
uv run pytest tests/triage/test_dupes.py::test_returns_similar_issues_above_threshold_best_first
uv run triage -R owner/repo sync                   # CLI (also: dupes <n>, search, ask, digest, bench)
```

Local embeddings need `uv sync --extra local` (fastembed). Tests use fakes and never hit the network.

## Architecture

`action.yml` wraps the CLI as a GitHub Action (docs: `docs/github-action.md`). `triage/` is the new engine and CLI (spec: `docs/superpowers/specs/2026-10-06-issue-triage-design.md`); `src/` is the legacy FastAPI app, rebuilt on the engine in v0.3.

The legacy FastAPI app has two endpoints, defined in `src/app.py`:

- `POST /scan {repo}` → `ScanService` fetches open issues via `GitHubClient` (PyGithub, skips PRs) and upserts `Repo` + `Issue` rows into SQLite.
- `POST /analyze {repo, prompt}` → `AnalyzeService` loads cached issues from SQLite and sends them to `OpenAIClient` (chat completions). Returns 404 if the repo was never scanned.

Layers: `src/app.py` (routes) → `src/services/{scan,analyze}/` (`service.py` + Pydantic `schema.py` per feature) → `src/libs/` (external API wrappers) and `src/models/database.py` (SQLAlchemy ORM). `src/database/connection.py` holds the async engine (`sqlite+aiosqlite`, `NullPool`), the `get_db_session` FastAPI dependency (commits on success, rolls back on error), and `init_database()` which runs `create_all` at startup. There are no migrations; schema changes require deleting `github_issues.db`.

Non-obvious behavior:

- `/scan` short-circuits if the repo already exists in the DB and returns the cached count with a `message`. It never re-fetches from GitHub; delete the DB (or the repo row) to refresh.
- Issue primary key is `owner/repo#number`; `Issue.to_dict()` strips it back to the number.
- `OpenAIClient` caps input at the 200 most recent issues (`MAX_ISSUES_PER_ANALYSIS`) and truncates each body to 500 chars.
- `GitHubClient` and `OpenAIClient` are synchronous and called directly from async handlers, so they block the event loop.
- `src/config/settings.py` instantiates `Settings()` at import, and `app.py` instantiates both services at import. Importing `src.app` without `OPENAI_API_KEY` set fails.
- Repo name validation (`owner/repo` regex) is duplicated in both `schema.py` files.
- GitHub errors are mapped to `ValueError` (404 not found, 403 rate limit), which `/scan` turns into HTTP 400.
