# Remaining Issues Plan (v0.1 close-out, benchmarks, v0.3 server)

> Written 2026-10-12, after #46 and #47 merged. Covers every open issue except #10, which is promised to an outside contributor (JARVIS1069) and is left for them.

**Goal:** Close out v0.1 with real benchmark numbers, validate demand with maintainers, then ship v0.3: the Docker server rebuilt on the `triage` engine, with auth, safe defaults and a small web UI.

**Spec:** `docs/superpowers/specs/2026-10-06-issue-triage-design.md` (§6 surfaces, §11 proving it works, §13 out of scope, §14 existing code).

**GitHub issues:** #27, #9 (close-out); #23, #39, #40 (data and validation); #42, #3, #4, #5, #34 (v0.3); #36 (roadmap, tracks all of them).

## Order and gates

```
Phase 1  housekeeping ──────────────────────────────┐
Phase 2  #23 bench on 5 repos ─► #40 maintainer test ─► go/stop ─► Phase 4 v0.3 (#42 + #3 #4 #5, then #34)
Phase 3  #39 vscode scale run (after #23 sets the threshold; independent of #40)
```

The spec's rule is to prove value before building more. v0.2 was built before #40 finished (user's call, recorded in the v0.2 plan), so the #40 gate now applies to v0.3 instead.

## Global Constraints

Same as v0.1 and v0.2: Python 3.10, no network in tests (fakes only), sanitized posted text, never closes or edits issues, dry run by default, secrets only from env. One engine: the server calls `triage.commands`, `triage.search`, `triage.ask` and `triage.digest`; it does not reimplement them. Same config file (`.github/issue-triage.yml`) and index format (`index_path()` in `triage/cli.py`) as the CLI. Single repo per server instance (multi-tenancy, accounts and GitHub login are out of scope, §13).

## Phase 1: Housekeeping (no code)

1. **#27 Label suggestions.** Close as completed: #47 shipped `triage labels`, existing-labels-only suggestions, `bench --labels` precision/recall, and `labels.apply` off by default. Tick it on #36.
2. **#9 Test suite and CI.** Its acceptance criteria targeted the legacy `/scan` and `/analyze`, which v0.3 deletes. CI already runs `ruff` and `pytest tests/triage` on every PR plus an Action smoke job. Comment that legacy tests are superseded by the v0.3 server tests (Phase 4, task 8), then close.
3. **#36 Roadmap.** Tick #27 and #9; add #47 under "Later". Move #34 under v0.3 with the narrowed scope from task 9 below.

## Phase 2: Benchmarks and maintainer test

4. **#23 Duplicate benchmark runs.** The command exists (`triage bench`, tests in `tests/triage/test_bench.py`); what's missing is the data.
   - Repos (from `docs/maintainer-test.md`): astral-sh/uv, neovim/neovim, denoland/deno, python-poetry/poetry, microsoft/terminal.
   - Per repo, four runs: local embeddings, API embeddings, each with and without `--llm`. Write `benchmarks/<owner>__<repo>.md` with `--out`.
   - Add `benchmarks/README.md` summarizing recall@3 and false flag rate per repo and configuration against the targets (recall@3 ≥ 60%, false flags ≤ 10% on at least 4 of 5).
   - Set `DuplicatesConfig.threshold` (`triage/config.py:20`, currently `0.86`) to the recommended threshold for the default (local) model; update the spec §8 example, `docs/github-action.md` and the README to match.
   - If targets are missed: record that on #23, try the API embedding model as the recommended default, and revisit before #40.
   - Needs: `GITHUB_TOKEN`, an embeddings/LLM key for the API runs. Run locally, not in CI.
5. **#40 Two-week maintainer test.** Human work, process already in `docs/maintainer-test.md`. Produce the five reports with the tuned threshold, send them, fill the log, copy it to #40 and record go/stop. Update the issue text: the gate now decides whether to build v0.3, not the Action.

## Phase 3: Scale run on microsoft/vscode (#39)

6. **Measurement support (small code change).** The README table needs "API calls used", which nothing tracks today.
   - `GitHubClient`: count requests (`self.requests`) and expose the last seen `X-RateLimit-Remaining`.
   - `triage sync` prints elapsed time and API calls; `triage search` gains a `--timing` flag (or the report records `time` output) for query latency.
   - Tests: request counter increments per page and per retry; sync summary line includes both numbers.
7. **The run.** `triage sync` on microsoft/vscode, interrupted once mid-run and resumed (acceptance: "can resume"). Then `bench` and `digest` with the threshold from task 4. Record sync time, API calls, index file size, p50/p95 query latency over 20 queries, and bench metrics. Add a "Scale" section to the README with the table and exact commands, and `benchmarks/microsoft__vscode.md`.

## Phase 4: v0.3 Docker server (after a "go" on #40)

Replaces the legacy app in `src/` (spec §14). The legacy `/scan` and `/analyze`, SQLAlchemy models, PyGithub and the OpenAI wrapper are deleted; #4 and #5 are fixed by building the new server correctly rather than patching code that is about to go.

8. **Server skeleton and safe defaults (#42, #4, #5).**
   - `src/app.py`: `create_app(settings) -> FastAPI` factory. No settings or services built at import, so tests need no keys (the problem #9 noted).
   - `src/settings.py`: `TRIAGE_REPO`, `TRIAGE_CONFIG` (default `.github/issue-triage.yml`), `TRIAGE_INDEX_DIR`, `TRIAGE_HOST` (default `127.0.0.1`), `TRIAGE_PORT` (8000), `TRIAGE_RELOAD` (false), `TRIAGE_CORS_ORIGINS` (empty: no CORS middleware), `TRIAGE_WEBHOOK_SECRET`, `TRIAGE_API_KEYS`. `main.py` reads host, port and reload from these.
   - Engine calls are synchronous, so they run in a single worker thread per repo (`concurrent.futures.ThreadPoolExecutor(max_workers=1)`), which also serializes SQLite writes. Request handlers await them via `run_in_executor`.
   - Errors (#4): middleware assigns `X-Request-ID` to every request and logs it; the exception handler returns `{"detail": "Internal server error", "request_id": ...}` with no exception text. Engine errors in `EXPECTED_ERRORS` map to 4xx with their own message (they are written for users). No prompt or issue content is logged at INFO.
   - Endpoints: `GET /healthz` (open), `GET /api/status` (repo, issue count, last sync, index size), `POST /api/sync`, `GET /api/search?q=&state=&label=&since=&limit=`, `POST /api/ask {question}`, `GET /api/digest` (preview, never posts).
   - Remove `sqlalchemy`, `aiosqlite`, `greenlet`, `PyGithub`, `pydantic-settings` if unused; delete `src/services`, `src/models`, `src/database`, `src/libs`. Bump the version, rewrite the README "Legacy server" section, update CLAUDE.md's architecture section.
9. **Webhooks (#42).** `POST /webhook`: verify `X-Hub-Signature-256` (HMAC-SHA256 of the raw body with `TRIAGE_WEBHOOK_SECRET`, `hmac.compare_digest`), reject with 401 otherwise; reject if the payload repo is not `TRIAGE_REPO`. On `issues` `opened`/`edited`: queue `check_duplicates` and, if enabled, `check_labels` on the worker; return 202 at once (GitHub times out at 10 s). Honour `dry_run` exactly like the CLI. Ignore other events with 204.
10. **Digest scheduler (#42).** No new dependency: an asyncio task started in the app lifespan that sleeps until the next `TRIAGE_DIGEST_SCHEDULE` slot (`"mon 09:00"` UTC, empty to disable) and then queues the same sync → embed → `build_digest` → post-or-print flow as `_digest` in `triage/cli.py`. Move that flow into `triage/commands.py` (`run_digest`) so the CLI and server share it.
11. **API keys and rate limits (#3).**
    - `TRIAGE_API_KEYS`: comma-separated `name:sha256hex` pairs (keys stored hashed; `triage server hash-key` prints the hash). Required on every `/api/*` route via `Authorization: Bearer <key>`; missing or wrong key returns 401. `/healthz` and `/webhook` (HMAC instead) are exempt. If no keys are configured and the host is not loopback, refuse to start.
    - Per-key token bucket in memory (`TRIAGE_RATE_LIMIT`, default `60/min`); 429 with `Retry-After`.
    - Daily LLM budget for `/api/ask` per key (`TRIAGE_ASK_DAILY_CALLS`, default 100), counted from `ChatModel` call counters; 429 with `Retry-After` until UTC midnight.
12. **Docker image and compose (#42).** `Dockerfile` (python:3.12-slim, `uv sync --frozen --extra local`, non-root user, `TRIAGE_HOST=0.0.0.0` set in the image because a container must listen on all interfaces, port 8000, volume `/data` for the index and `FASTEMBED_CACHE_PATH`). `docker-compose.yml` mounting `.github/issue-triage.yml` read-only and `/data`, env from `.env`. `docs/docker-server.md`: setup, creating the webhook (content type JSON, secret, "Issues" events), generating API keys, exposing it behind a reverse proxy. CI job builds the image and hits `/healthz`.
13. **Tests (closes the gap behind #9).** `tests/server/` with `fastapi.testclient.TestClient` and the existing fakes in `tests/triage/helpers.py`: unsigned or wrongly signed webhook → 401; other-repo payload rejected; `opened` queues a duplicate check and respects dry run; 401 without key, 200 with key; 429 with `Retry-After` past the limit and past the ask budget; 500 body has a request ID and no exception text; CORS headers absent by default and present for a configured origin; `create_app` imports with no env set; scheduler computes the next slot correctly across week boundaries. CI: `uvx ruff check triage src tests`, `uv run pytest`.
14. **Web UI (#34, narrowed).** Single repo, no "connect a repo" (accounts and multi-tenancy are out of scope, §13). Server-rendered pages without a JS build step: status (sync time, counts), search, Ask with linked citations, themes (from `build_digest`), recent duplicate flags. The flags view needs a `posted` table in the store (issue, kind, comment id, candidates, time) written by `post_or_update`; the spec §7.2 already lists posted-comment records. The UI uses the same API key, entered once and kept in `sessionStorage`. Comment on #34 with the narrowed scope before starting.

## Done when

- #27 and #9 closed; #23 has 5 published reports and a tuned default; #39 README table published; #40 log and decision recorded.
- `docker compose up` serves the configured repo; a signed `issues.opened` webhook posts (or dry-runs) the same comment the Action would; unsigned webhooks and keyless API calls are refused.
- #3, #4, #5, #34, #42 closed by the v0.3 PRs; #36 fully ticked and closed.

## Suggested PRs

1. Phase 1: issue comments only, no PR.
2. `bench-results`: task 4 (reports, tuned threshold, docs).
3. `scale-run`: tasks 6 and 7.
4. `server-core`: tasks 8, 9, 10, 13 (closes #42 except Docker, #4, #5).
5. `server-auth`: task 11 (closes #3).
6. `server-docker`: task 12 (closes #42).
7. `server-ui`: task 14 (closes #34).
