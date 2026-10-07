# Open Source Ecosystem MVP Plan

> **Superseded** by `docs/superpowers/specs/2026-10-06-issue-triage-design.md` after the LLM council review. Kept for reference only; do not execute.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. This is the master plan: before executing a milestone, write its step-level TDD plan to `docs/superpowers/plans/` using the task definitions, interfaces and tests below. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One platform where a developer signs in with GitHub and gets (a) open source issues recommended from their GitHub profile and (b) answers about any public repo's issue tracker, with cited issues, at the scale of `microsoft/vscode`.

**Architecture:** One Python backend (this repo, `github-issues-analyzer`) serves both products from one API, one Postgres + pgvector database, one Arq worker and one GitHub OAuth login. One web frontend (`open-source-project-finder`, rebuilt) has two sections: **Discover** (contributor recommendations) and **Analyze** (maintainer questions). Both are served from the same origin behind Caddy, so the session cookie works without cross-site settings.

**Tech Stack:** Python 3.10+, uv, FastAPI, SQLAlchemy 2 async + asyncpg, Alembic, Postgres 16 + pgvector, Redis + Arq, httpx (GitHub REST and GraphQL), OpenAI SDK against any OpenAI-compatible endpoint, cryptography (Fernet), Vite + vanilla TypeScript, Caddy, Docker Compose, GitHub Actions.

**Spec:** This document. Design discussion is captured in the roadmap issue [#36](https://github.com/OptimusRahul/github-issues-analyzer/issues/36) and issues #3 to #37.

## Global Constraints

- GitHub OAuth App with scope `read:user` only. No `repo` scope in the MVP; only public data is read.
- OAuth code exchange happens on the server. No client secret or token ever reaches the browser.
- GitHub access tokens are stored encrypted (Fernet, key from `TOKEN_ENCRYPTION_KEY`).
- Every GitHub call made for a user uses that user's token, so each user spends their own rate limit.
- All GitHub HTTP goes through one module: `src/libs/github_client.py`.
- All LLM and embedding calls go through one module: `src/libs/llm.py`, configured per task with `base_url`, `api_key` and `model` (OpenAI-compatible, so open-weight models work).
- Frontend renders API data with `textContent` or escaped templates only. Never `innerHTML` with issue or LLM text.
- Settings are loaded lazily; importing the app must not require any secret.
- Repository keys are the canonical lowercased `full_name` returned by GitHub.
- Same origin for frontend and API in every environment (Vite proxy in dev, Caddy in prod).

## MVP Scope

**Analyze (maintainers), in scope:** sign in, add any public repo, watch sync progress, ask questions and get answers that cite real issues, search issues, daily refresh.
**Out of scope:** clustering and themes (#25), duplicate detection (#26), label suggestions (#27), digests (#28), GitHub App and webhooks (#29), billing (#31), Slack (#35), streaming, reranker.

**Discover (contributors), in scope:** sign in, profile summary (languages, topics, experience level), top 20 recommended open issues with reasons, language filter, save and dismiss, manual refresh, language picker when the profile is empty.
**Out of scope:** embedding-based personalisation, learned ranking, weekly email, maintainer-to-contributor matching.

**MVP success measures:**
- Backfill of `microsoft/vscode` open issues plus 90 days of closed issues completes, and a killed worker resumes without refetching finished pages.
- `/ask` answers in under 10 s at p95 and every returned citation is an issue that was retrieved.
- Recommendations load in under 5 s from cache and under 20 s cold, and never include archived repos or repos with no push in 180 days.

## Review Focus

1. **New user with no public repos or stars.** Expected: Discover shows a language picker, saves the choice, and returns recommendations from it. Test owner: Task 4.1 (`test_empty_profile_marks_needs_onboarding`) and Task 4.4 (`test_recommendations_use_language_override`).
2. **Revoked or expired GitHub token.** Expected: any GitHub 401 for a user clears their session and the API returns 401 `reauth_required`; the frontend sends them to login. Test owner: Task 1.2 (`test_github_401_forces_reauth`).
3. **GitHub search rate limit (30 per minute per user).** Expected: recommendations come from cache when fresh; on 403/429 from search, return cached results with `stale: true`, or 503 with `Retry-After` if there is no cache. Test owner: Task 4.2 (`test_search_rate_limit_falls_back_to_cache`).
4. **Issue or answer text containing HTML or script.** Expected: shown as plain text. Test owner: Task 5.1 (`render.test.ts: escapes issue title and body`).
5. **Repo renamed, transferred or made private during or after sync.** Expected: rename and transfer resolve to the new canonical name and keep data; private or deleted returns a clear 404 and marks the repo `unavailable`. Test owner: Task 0.4 (`test_resolve_repo_follows_rename`, `test_resolve_repo_private_is_not_found`) and Task 2.2 (`test_backfill_marks_repo_unavailable_on_404`).

---

## File Structure

### Backend (`github-issues-analyzer`)

```
docker-compose.yml              postgres (pgvector/pgvector:pg16), redis
alembic.ini, migrations/        Alembic env + versions
src/
  app.py                        FastAPI app, middleware, router includes
  config/settings.py            lazy get_settings() (lru_cache)
  database/connection.py        asyncpg engine, get_db_session
  models/                       SQLAlchemy models, one file per area
    user.py  repo.py  issue.py  chunk.py  job.py  finder.py
  auth/
    router.py                   /auth/login, /auth/callback, /auth/logout, /me
    crypto.py                   encrypt_token / decrypt_token
    deps.py                     current_user dependency, rate limit
  libs/
    github_client.py            async httpx client: REST pagination, GraphQL, rate limits
    llm.py                      chat_json(), embed() per task config
  analyze/
    router.py                   /repos, /jobs, /repos/{o}/{r}/search, /ask
    sync.py                     backfill + refresh jobs
    chunking.py                 chunk_issue()
    search.py                   hybrid_search()
    answer.py                   answer_question()
  finder/
    router.py                   /finder/*
    profile.py                  build_profile()
    candidates.py               fetch_candidates()
    scoring.py                  score_candidates() (pure)
  worker.py                     Arq WorkerSettings, cron
evals/run.py                    recall@k over fixtures
tests/                          mirrors src/ layout
```

Removed: `src/services/`, `src/libs/openai_client.py`, PyGithub, `main.py` (replaced by `uv run uvicorn src.app:app`), `PROJECT_SUMMARY.md`.

### Frontend (`open-source-project-finder`)

```
index.html
vite.config.ts                  dev proxy /api and /auth to :8000
src/
  main.ts                       router: /login, /discover, /analyze
  api.ts                        fetch wrapper, 401 -> /login
  render.ts                     el(tag, props, children) using textContent only
  pages/login.ts  pages/discover.ts  pages/analyze.ts
  style.css
deploy/Caddyfile
```

Removed: `index.js`, `public/js/script.js` (contains a leaked OAuth secret), `public/js/bundle.js*`, Express, Parcel.

### Data model

| Table | Key columns |
|---|---|
| `users` | `id`, `github_id` unique, `login`, `avatar_url`, `token_encrypted`, `created_at`, `last_login_at` |
| `repos` | `id`, `github_id` unique, `full_name` unique (lowercased), `archived`, `pushed_at`, `topics` jsonb, `stars`, `status` (`active`, `unavailable`), `last_synced_at`, `metadata_fetched_at` |
| `user_repos` | `user_id`, `repo_id` (repos a user tracks in Analyze) |
| `issues` | `id`, `repo_id`, `number`, `title`, `body`, `state`, `state_reason`, `labels` jsonb, `comments_count`, `reactions_total`, `author_association`, `html_url`, `created_at`, `updated_at`, `closed_at`; unique (`repo_id`, `number`) |
| `comments` | `id` (GitHub id), `issue_id`, `body`, `author_association`, `created_at`, `updated_at` |
| `chunks` | `id`, `issue_id`, `ordinal`, `text`, `content_hash`, `embedding` vector(`EMBEDDING_DIM`), `embedding_model`, `tsv` generated tsvector; HNSW index on `embedding`, GIN on `tsv` |
| `sync_jobs` | `id`, `repo_id`, `user_id`, `kind` (`backfill`, `refresh`), `status` (`queued`, `running`, `done`, `failed`), `cursor` jsonb, `pages_done`, `items_done`, `error`, `started_at`, `finished_at` |
| `profiles` | `user_id`, `languages` jsonb (name to weight), `topics` jsonb, `merged_prs`, `level` (`first_timer`, `beginner`, `experienced`), `language_override` jsonb, `needs_onboarding`, `built_at` |
| `candidate_cache` | `user_id`, `items` jsonb, `fetched_at` |
| `feedback` | `user_id`, `issue_url`, `action` (`saved`, `dismissed`), `created_at`; unique (`user_id`, `issue_url`) |
| `usage` | `user_id`, `task`, `model`, `input_tokens`, `output_tokens`, `created_at` |

---

## Milestone 0: Foundations (backend)

Covers #4, #5, #6, #7, #8, #9, #10, #16.

### Task 0.1: Lazy settings, test harness and CI

**Files:** Modify `src/config/settings.py`, `pyproject.toml`. Create `tests/conftest.py`, `.github/workflows/ci.yml`. Delete `PROJECT_SUMMARY.md`.

**Interfaces:**
- Produces: `get_settings() -> Settings` (cached). Settings fields: `database_url`, `redis_url`, `github_client_id`, `github_client_secret`, `token_encryption_key`, `session_secret`, `cors_origins: list[str] = []`, `llm_*` per task (Task 3.1), `embedding_dim: int = 512`.
- Produces: pytest fixtures `db_session` (transaction rolled back per test, Postgres from `TEST_DATABASE_URL`), `client` (httpx `AsyncClient` on the app), `logged_in_client(user)`.

**Tests:**
- `test_app_imports_without_env`: importing `src.app` with an empty environment succeeds.
- CI runs `uvx ruff check .` and `uv run pytest` with a `pgvector/pgvector:pg16` service container.

### Task 0.2: Postgres, Alembic and the MVP schema

**Files:** Create `docker-compose.yml`, `alembic.ini`, `migrations/`, `src/models/*.py`. Modify `src/database/connection.py`. Add deps `asyncpg`, `alembic`, `pgvector`; remove `aiosqlite`.

**Interfaces:**
- Produces: every table in the Data model section; `get_db_session()` unchanged in shape.
- `create_all` is removed from startup; `uv run alembic upgrade head` is the only way to create the schema.

**Tests:**
- `test_migrations_upgrade_and_downgrade`: `upgrade head` then `downgrade base` succeeds on an empty database.
- `test_issue_unique_per_repo_number`: inserting the same (`repo_id`, `number`) twice raises `IntegrityError`.

### Task 0.3: Security hygiene

**Files:** Modify `src/app.py`.

**Interfaces:**
- Produces: request ID middleware setting `X-Request-ID`; global handler returning `{"detail": "internal_error", "request_id": ...}`.
- CORS origins from `cors_origins`. Server started with `uv run uvicorn src.app:app --host 127.0.0.1`.

**Tests:**
- `test_500_hides_exception_text`: a route raising `RuntimeError("secret")` returns 500 without `secret` in the body and with a `request_id`.
- `test_prompt_max_length`: request models reject over-long text fields with 422 (shared validator used by Task 3.4).

### Task 0.4: Async GitHub client

**Files:** Rewrite `src/libs/github_client.py`. Create `tests/libs/test_github_client.py`. Make `httpx` a main dependency; remove `PyGithub`.

**Interfaces:**
- Produces: `class GitHubClient(token: str, transport: httpx.AsyncBaseTransport | None = None)`
  - `async resolve_repo(full_name: str) -> RepoInfo` (`github_id`, `full_name` lowercased, `archived`, `pushed_at`, `topics`, `stars`, `private`)
  - `async paginate(path: str, params: dict, cursor: str | None = None) -> AsyncIterator[Page]` where `Page = (items: list[dict], next_cursor: str | None)`, `per_page=100`, cursor is the `Link: rel="next"` URL
  - `async graphql(query: str, variables: dict) -> dict`
  - `async search_issues(q: str, per_page: int = 50) -> list[dict]`
- Errors: `RepoNotFound`, `RateLimited(reset_at: datetime)`, `ReauthRequired`, `GitHubError`.
- Behaviour: on `X-RateLimit-Remaining: 0` or a secondary limit with `Retry-After`, raise `RateLimited` with the reset time (the caller decides to wait or reschedule). 401 raises `ReauthRequired`. 404 raises `RepoNotFound`.

**Tests** (all with `httpx.MockTransport`, no network):
- `test_paginate_follows_link_header_and_uses_per_page_100`
- `test_paginate_resumes_from_cursor`
- `test_rate_limit_raises_with_reset_time`
- `test_resolve_repo_follows_rename` (301 to new repo returns new `full_name`)
- `test_resolve_repo_private_is_not_found`
- `test_401_raises_reauth_required`

---

## Milestone 1: GitHub login (shared)

Covers #3 (replaced by login sessions) and the login part of #29.

### Task 1.1: OAuth login, session and disconnect

**Files:** Create `src/auth/router.py`, `src/auth/crypto.py`, `tests/auth/test_router.py`. Modify `src/app.py` (add `SessionMiddleware`, `https_only` outside dev, `same_site="lax"`).

**Interfaces:**
- Produces: `GET /auth/login` (redirect to GitHub with random `state` stored in session, scope `read:user`), `GET /auth/callback?code&state` (verify state, exchange code server-side, fetch `/user`, upsert `users`, store encrypted token, set `session["user_id"]`, redirect to `/discover`), `POST /auth/logout`, `GET /me` (`{login, avatar_url}`), `DELETE /me` (revoke grant via `DELETE /applications/{client_id}/grant`, delete user and all user rows).
- Produces: `encrypt_token(str) -> bytes`, `decrypt_token(bytes) -> str`.

**Tests:**
- `test_callback_rejects_bad_state`
- `test_callback_creates_user_and_encrypts_token` (stored value differs from the token and decrypts back to it)
- `test_delete_me_removes_user_data_and_revokes_grant`

### Task 1.2: Current user dependency and per-user rate limit

**Files:** Create `src/auth/deps.py`, `tests/auth/test_deps.py`.

**Interfaces:**
- Produces: `async current_user(request, db) -> User` (401 if no session), `async github_for(user) -> GitHubClient`, `rate_limit(key: str, per_minute: int)` dependency (Redis `INCR` with 60 s expiry, 429 with `Retry-After`).
- Produces: exception handler mapping `ReauthRequired` to 401 `{"detail": "reauth_required"}` and clearing the session.

**Tests:**
- `test_unauthenticated_request_is_401`
- `test_github_401_forces_reauth`
- `test_rate_limit_returns_429_after_limit`

---

## Milestone 2: Analyze ingestion at scale

Covers #11, #12, #13, #14, #15, #17.

### Task 2.1: Worker, repos and jobs API

**Files:** Create `src/worker.py`, `src/analyze/router.py`, `tests/analyze/test_router.py`. Delete `src/services/`.

**Interfaces:**
- Produces: `POST /repos {full_name}` resolves the repo with the user's token, links `user_repos`, creates a `sync_jobs` row and enqueues `backfill_repo(job_id)`; returns `202 {job_id, repo}`. If a backfill already ran, returns `200` with the repo and enqueues nothing.
- Produces: `GET /repos` (user's repos with `status`, `last_synced_at`, issue count via `COUNT`), `GET /jobs/{id}` (`status`, `pages_done`, `items_done`, `error`).
- Worker run command: `uv run arq src.worker.WorkerSettings`.

**Tests:**
- `test_post_repo_returns_202_and_enqueues_once`
- `test_post_repo_canonicalises_name` (`Facebook/React` stored as `react/react`)
- `test_get_repos_counts_without_loading_rows`

### Task 2.2: Backfill job with checkpoints

**Files:** Create `src/analyze/sync.py`, `tests/analyze/test_sync.py`.

**Interfaces:**
- Produces: `async backfill_repo(ctx, job_id: int) -> None`. Phases stored in `cursor`: `open_issues`, `closed_issues` (`state=closed&since=now-90d`), `comments` (repo-wide `/issues/comments?since=now-90d`). After each page: bulk upsert with `INSERT ... ON CONFLICT` (pull requests skipped), then save `cursor` and counters in the same transaction. On `RateLimited`, re-enqueue itself with `_defer_until=reset_at`. On `RepoNotFound`, mark repo `unavailable` and job `failed`. On finish, set `last_synced_at` and enqueue `embed_repo(repo_id)`.

**Tests:**
- `test_backfill_stores_issues_and_skips_pull_requests`
- `test_backfill_resumes_from_checkpoint_after_crash` (MockTransport fails on page 3; rerun fetches only pages 3 onwards)
- `test_backfill_defers_on_rate_limit`
- `test_backfill_marks_repo_unavailable_on_404`
- `test_backfill_200_pages_uses_200_requests` (vscode-scale simulation: 20,000 issues)

### Task 2.3: Incremental refresh

**Files:** Modify `src/analyze/sync.py`, `src/worker.py`, `src/analyze/router.py`.

**Interfaces:**
- Produces: `async refresh_repo(ctx, repo_id: int)` fetching issues and comments with `state=all&since=last_synced_at`; `POST /repos/{owner}/{repo}/refresh` (rate limited to once per 10 minutes per repo); Arq cron at 03:00 UTC refreshing every `active` repo.

**Tests:**
- `test_refresh_uses_since_last_synced_at`
- `test_refresh_marks_closed_issues_closed`

---

## Milestone 3: Analyze answers (RAG)

Covers #19, #20 (without reranker), #21 (without streaming), #23 (minimal), #24, and the config part of #37.

### Task 3.1: Per-task LLM and embedding configuration

**Files:** Create `src/libs/llm.py`, `tests/libs/test_llm.py`. Delete `src/libs/openai_client.py`.

**Interfaces:**
- Settings per task `answer` and `embed`: `LLM_ANSWER_BASE_URL`, `LLM_ANSWER_API_KEY`, `LLM_ANSWER_MODEL`, `LLM_EMBED_BASE_URL`, `LLM_EMBED_API_KEY`, `LLM_EMBED_MODEL`, plus `EMBEDDING_DIM`.
- Produces: `async chat_json(task: str, system: str, user: str, schema: dict, user_id: int | None) -> dict` (JSON schema response format where supported, validates the result, retries once on invalid JSON, records `usage`), `async embed(texts: list[str]) -> list[list[float]]` (batches of 100, asserts vector length equals `EMBEDDING_DIM`).

**Tests:**
- `test_chat_json_retries_once_on_invalid_json`
- `test_embed_rejects_wrong_dimension`
- `test_base_url_is_configurable` (requests go to the configured host)

### Task 3.2: Chunking and embedding job

**Files:** Create `src/analyze/chunking.py`, `tests/analyze/test_chunking.py`. Modify `src/analyze/sync.py`.

**Interfaces:**
- Produces: `chunk_issue(issue, comments, max_chars=2000) -> list[Chunk]` where each chunk text starts with `#{number} {title}` and the chunks cover the body then comments in order; secrets matching common token patterns (`ghp_`, `sk-`, AWS keys) are replaced with `[redacted]`.
- Produces: `async embed_repo(ctx, repo_id: int)` embedding only chunks whose `content_hash` changed.

**Tests:**
- `test_chunk_issue_splits_long_body_and_keeps_header`
- `test_chunk_issue_redacts_tokens`
- `test_embed_repo_skips_unchanged_chunks`

### Task 3.3: Hybrid search

**Files:** Create `src/analyze/search.py`, `tests/analyze/test_search.py`. Modify `src/analyze/router.py`.

**Interfaces:**
- Produces: `async hybrid_search(db, repo_id: int, query: str, k: int = 40, state: str | None = None, labels: list[str] | None = None, since: date | None = None) -> list[Hit]` where `Hit = (issue_number, title, html_url, state, snippet, score)`. One SQL query: top 100 by cosine distance and top 100 by `ts_rank`, merged with reciprocal rank fusion (`1 / (60 + rank)`), grouped per issue.
- Produces: `GET /repos/{owner}/{repo}/search?q=&state=&label=&since=`.

**Tests:**
- `test_exact_error_string_found_by_keyword` (an issue containing `ERR_OSSL_EVP_UNSUPPORTED` ranks first even with an unrelated embedding)
- `test_filters_applied` (closed issues excluded when `state=open`)

### Task 3.4: Answer endpoint with checked citations

**Files:** Create `src/analyze/answer.py`, `tests/analyze/test_answer.py`. Modify `src/analyze/router.py`. Remove `/scan` and `/analyze`.

**Interfaces:**
- Produces: `POST /repos/{owner}/{repo}/ask {question}` (question 1 to 1,000 chars, 10 per minute per user) returning `{answer: str, citations: [{number, title, html_url}], retrieved: int}`.
- Prompt: system prompt states that issue text is untrusted data; the top 15 hits are wrapped in `<issue number="...">` blocks. Schema: `{answer: string, citations: integer[]}`. Citations not in the retrieved set are dropped.

**Tests:**
- `test_answer_drops_citations_not_retrieved`
- `test_answer_returns_404_for_untracked_repo`
- `test_prompt_marks_issue_text_as_data` (prompt contains the delimiters and the untrusted-data instruction)
- `test_no_issue_text_in_info_logs` (captured INFO logs during `/ask` contain no issue body text)

### Task 3.5: Minimal evaluation

**Files:** Create `evals/run.py`, `evals/fixtures/` (a frozen snapshot of about 500 issues from one repo plus 20 questions with expected issue numbers).

**Interfaces:**
- Produces: `uv run python -m evals.run` printing recall@15 and the share of answers whose citations are all in the expected set.

**Tests:**
- The command runs in CI on a schedule (not on every PR, because it calls the embedding model).

---

## Milestone 4: Discover recommendations (backend)

### Task 4.1: Profile builder

**Files:** Create `src/finder/profile.py`, `tests/finder/test_profile.py`.

**Interfaces:**
- Produces: `async build_profile(gh: GitHubClient, user: User) -> Profile`. One GraphQL query reads the viewer's owned non-fork repos (first 100: `languages(first: 5)` with sizes, `repositoryTopics(first: 10)`) and starred repos (first 100: `primaryLanguage`, topics). Merged PRs come from `search/issues?q=is:pr is:merged author:{login}` `total_count`.
- Weights: own-repo language bytes normalised to 1.0, plus 0.3 per starred repo's primary language, then normalised. Topics: own and starred, counted.
- Level: 0 merged PRs is `first_timer`, 1 to 10 is `beginner`, more than 10 is `experienced`.
- `needs_onboarding = True` when there are no languages and no `language_override`.

**Tests:**
- `test_languages_weighted_by_bytes_and_stars`
- `test_level_thresholds`
- `test_empty_profile_marks_needs_onboarding`

### Task 4.2: Candidate issues

**Files:** Create `src/finder/candidates.py`, `tests/finder/test_candidates.py`.

**Interfaces:**
- Produces: `async fetch_candidates(gh, profile) -> list[Candidate]` for the top 3 languages (or `language_override`). Query per language: `is:issue is:open no:assignee -linked:pr archived:false language:{lang} updated:>{today-60d}` plus `label:"good first issue"` for `first_timer` and `beginner`, or `label:"help wanted"` for `experienced`. Up to 50 per language, deduplicated by URL. Results cached in `candidate_cache` for 6 hours.
- Repo health: for at most 30 unique repos, use `repos` metadata if `metadata_fetched_at` is under 24 hours old, otherwise `resolve_repo`. Drop archived repos and repos with no push in 180 days.

**Tests:**
- `test_query_uses_level_label_and_excludes_linked_prs`
- `test_drops_archived_and_inactive_repos`
- `test_search_rate_limit_falls_back_to_cache`

### Task 4.3: Scoring with reasons

**Files:** Create `src/finder/scoring.py`, `tests/finder/test_scoring.py`.

**Interfaces:**
- Produces: `score_candidates(profile, candidates, dismissed: set[str]) -> list[Recommendation]` (pure, no I/O). `Recommendation = (candidate, score: float, reasons: list[str])`.
- Score = 0.35 × language weight + 0.25 × topic overlap (Jaccard of profile topics and repo topics) + 0.20 × level fit (label matches level) + 0.10 × freshness (linear from updated today to 60 days) + 0.10 × repo activity (pushed within 7 days is 1.0, down to 0 at 180 days). Dismissed URLs removed. Reasons name the strongest factors, for example "You write Python" or "Matches your interest in cli".

**Tests:**
- `test_language_match_ranks_higher`
- `test_dismissed_issues_removed`
- `test_reasons_name_top_factors`
- `test_scores_between_0_and_1`

### Task 4.4: Discover API

**Files:** Create `src/finder/router.py`, `tests/finder/test_router.py`.

**Interfaces:**
- Produces: `GET /finder/profile`, `PUT /finder/profile/languages {languages: [str]}` (sets `language_override`, max 5), `GET /finder/recommendations?language=` (top 20, `{items, stale, built_at}`), `POST /finder/feedback {issue_url, action}`, `GET /finder/saved`, `POST /finder/refresh` (rebuild profile and candidates; once per 10 minutes).

**Tests:**
- `test_recommendations_use_language_override`
- `test_feedback_dismiss_hides_issue`
- `test_refresh_is_rate_limited`

---

## Milestone 5: Web app (`open-source-project-finder`)

### Task 5.1: Replace the old app

**Files:** Delete `index.js`, `public/`, Express and Parcel from `package.json`. Create the frontend layout above. Add `vitest`.

**Interfaces:**
- Produces: `el(tag, props, children)` that sets text with `textContent` and only allows `href` values starting with `https://github.com/`.
- `vite.config.ts` proxies `/api/*` to `http://127.0.0.1:8000` with the `/api` prefix removed (same as Caddy), and `/auth/*` unchanged. Backend routes therefore have no `/api` prefix.

**Tests:**
- `render.test.ts: escapes issue title and body` (`<img onerror>` renders as text)
- `render.test.ts: rejects non-GitHub links`

The leaked OAuth secret must already be reset in GitHub before this task (see Pre-work).

### Task 5.2: Login and session

**Files:** `src/pages/login.ts`, `src/api.ts`, `src/main.ts`.

**Interfaces:**
- `api.ts` sends `credentials: "same-origin"`; any 401 redirects to `/login`. Login button links to `/auth/login`. Header shows avatar and a disconnect button calling `DELETE /api/me` after an in-page confirmation.

**Tests:**
- `api.test.ts: 401 redirects to login`

### Task 5.3: Discover page

**Files:** `src/pages/discover.ts`.

**Behaviour:** profile summary (top languages, level); onboarding language picker when `needs_onboarding`; recommendation cards (repo, issue title, labels, age, reasons, open-on-GitHub link, Save and Dismiss); language filter; Saved tab; Refresh button; "Showing cached results" note when `stale`.

**Tests:**
- `discover.test.ts: shows language picker when needs_onboarding`
- `discover.test.ts: dismiss removes card`

### Task 5.4: Analyze page

**Files:** `src/pages/analyze.ts`.

**Behaviour:** add repo form; repo list with status and progress (polls `/api/jobs/{id}` every 3 s while running); per-repo ask box showing the answer as plain text and citations as links; search box with state filter.

**Tests:**
- `analyze.test.ts: polls job until done`
- `analyze.test.ts: renders citations as GitHub links`

### Task 5.5: Deployment

**Files:** `deploy/Caddyfile` (frontend repo); `docker-compose.prod.yml` (backend repo: api, worker, postgres, redis, caddy).

**Behaviour:** one VM. Caddy serves `dist/` and proxies `/api/*` (prefix stripped) and `/auth/*` to the API. HTTPS via Caddy. Migrations run before the API starts. Nightly `pg_dump` to object storage.

**Tests:**
- Smoke script `deploy/smoke.sh` checks `/api/healthz`, the login redirect, and that static files are served.

---

## Milestone 6: Launch readiness

### Task 6.1: Operations basics

**Files:** Modify `src/app.py`, `src/worker.py`.

**Behaviour:** JSON logs with request ID and user ID; `/api/healthz` checks database and Redis; per-user daily token budget from `usage` (429 when exceeded); privacy page text stating that only public data is read and how to disconnect.

**Tests:**
- `test_token_budget_exceeded_returns_429`
- `test_healthz_reports_db_down`

### Task 6.2: Scale run on staging

**Behaviour:** add `microsoft/vscode` on staging and record backfill time, request count, resume after killing the worker, `/ask` p95 over 50 questions, and recommendation latency for three real accounts (no repos, beginner, experienced). Results go in `docs/mvp-scale-run.md`. Any missed success measure becomes an issue before launch.

---

## Pre-work (before Milestone 0)

- [ ] Reset the OAuth client secret that is committed in `open-source-project-finder/public/js/script.js`, and create a new OAuth App for this platform with callback `/auth/callback`.
- [ ] Generate `TOKEN_ENCRYPTION_KEY` (`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`) and `SESSION_SECRET`, and store them outside git.

## Order and dependencies

```
Pre-work -> M0 -> M1 -> M2 -> M3
                    \-> M4
M5.1-5.2 after M1; 5.3 after M4; 5.4 after M3
M6 after M3, M4, M5
```

M2/M3 (Analyze) and M4 (Discover) can be built in parallel once M1 is done.

## Mapping to existing GitHub issues

- **In the MVP:** #4, #5, #6, #7, #8, #9, #10, #11, #12, #13, #14, #15, #16, #17, #19, #20 (no reranker), #21 (no streaming), #23 (minimal), #24, #37 (configuration only), #18 (single VM), #34 (basic web app), #3 (replaced by GitHub login).
- **After the MVP:** #22, #25, #26, #27, #28, #29 (GitHub App and webhooks), #30, #31, #32, #33, #35. Discover needs new issues for embedding-based personalisation, learned ranking, weekly email and maintainer matching.
