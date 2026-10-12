# Issue triage server

The server runs the same engine as the CLI and the GitHub Action, with the same config file (`.github/issue-triage.yml`) and index files. It:

- checks new issues from a GitHub webhook (related issues, confirmed duplicates, label suggestions)
- syncs every `TRIAGE_SYNC_MINUTES` and posts the digest every `digest.window_days`
- serves search, Ask, related issues and the digest preview over an API with keys

## Run it with Docker

```bash
cp .env.example .env        # set TRIAGE_REPOS, GITHUB_TOKEN, TRIAGE_API_KEYS, TRIAGE_WEBHOOK_SECRET
touch .github/issue-triage.yml
docker compose up -d
curl -H "Authorization: Bearer $KEY" localhost:8000/api/repos
```

The index and the embedding model live in the `triage-data` volume. The port is published on localhost only. To receive webhooks, put a TLS reverse proxy (Caddy, nginx) in front of it.

Without Docker: `uv sync --extra server --extra local`, export the same variables, then `uv run triage serve` (listens on `127.0.0.1:8000`; `--host`, `--port`, `--reload`).

## Settings

| Variable | Default | |
|---|---|---|
| `TRIAGE_REPOS` | (required) | `owner/repo`, comma separated |
| `GITHUB_TOKEN` | | reads issues; needs `issues: write` to post when `dry_run: false` |
| `TRIAGE_API_KEYS` | none | sha256 hex of each API key; with none, every `/api` request is refused |
| `TRIAGE_WEBHOOK_SECRET` | none | with none, the webhook is refused |
| `TRIAGE_CORS_ORIGINS` | none | origins allowed to call the API from a browser |
| `TRIAGE_RATE_PER_MINUTE` | 60 | requests per API key |
| `TRIAGE_ASK_CALLS_PER_DAY` | 200 | LLM calls for Ask per day, all keys together |
| `TRIAGE_SYNC_MINUTES` | 60 | 0 turns the scheduler off |

Make a key: `key=$(openssl rand -hex 24); echo "$key"; printf %s "$key" | shasum -a 256`. Give the key to clients and put the hash in `TRIAGE_API_KEYS`.

## Dashboard

Open `http://localhost:8000/` and sign in with an API key. Pages:

- repositories with issue counts and last sync
- per repository: search, Ask with links to the cited issues, new and growing themes, and the latest open issues with their related issues (and label suggestions when `labels.enabled`)

Sessions last 12 hours and live in memory, so a restart signs everyone out. The session cookie is HttpOnly and SameSite=Strict, and pages send a Content Security Policy that only allows htmx from cdnjs.

## Webhook

In the repository settings, add a webhook to `https://your-host/webhook`, content type `application/json`, the same secret as `TRIAGE_WEBHOOK_SECRET`, and the **Issues** event. Every request's `X-Hub-Signature-256` is checked; only `issues` / `opened` for a configured repository does anything.

## API

All `/api` routes need `Authorization: Bearer <key>`. Interactive docs: `/api/docs`.

| Route | |
|---|---|
| `GET /health` | no key needed |
| `GET /api/repos` | repositories, issue counts, last sync |
| `POST /api/repos/{owner}/{repo}/sync` | sync now |
| `GET /api/repos/{owner}/{repo}/search?q=&state=&label=&since=&limit=` | hybrid search |
| `POST /api/repos/{owner}/{repo}/ask` `{"question": "..."}` | answer with checked citations |
| `GET /api/repos/{owner}/{repo}/issues/{n}/related` | related issues and label suggestions, no LLM, posts nothing |
| `GET /api/repos/{owner}/{repo}/digest` | the digest as Markdown, posts nothing |

Errors return `{"detail": ..., "request_id": ...}`. A 500 never contains exception text; find the request ID in the server log. Logs hold method, path, status and request ID only: no query strings, issue text, questions or prompts.
