# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Uses [uv](https://github.com/astral-sh/uv). Python >= 3.10.

```bash
uv sync                      # install deps (incl. dev: pytest, pytest-asyncio, httpx)
uv run triage serve          # server on 127.0.0.1:8000 (needs --extra server and TRIAGE_* env; see docs/server.md)
uvx ruff check triage tests  # lint (what CI runs); ruff is not in uv dev deps (config in pyproject)
uv run pytest tests/triage                         # triage engine tests
uv run pytest tests/triage/test_dupes.py::test_returns_similar_issues_above_threshold_best_first
uv run triage -R owner/repo sync                   # CLI (also: dupes <n>, search, ask, digest, bench)
```

Local embeddings need `uv sync --extra local` (fastembed). Tests use fakes and never hit the network.

## Architecture

`action.yml` wraps the CLI as a GitHub Action (docs: `docs/github-action.md`). `triage/` is the engine and CLI (spec: `docs/superpowers/specs/2026-10-06-issue-triage-design.md`). `triage/server.py` is the FastAPI server on the same engine (`triage serve`, `Dockerfile`, `compose.yaml`; docs: `docs/server.md`).

Non-obvious behavior:

- Duplicate comments list related issues; only candidates the confirm LLM accepts are called possible duplicates and get the label. A failed or over-budget LLM confirms nothing.
- The `embeddings` table is keyed on issue number, so one index file holds one embedding model's vectors. To compare models, copy the index and use `--index-dir`.
- Server: one `Store` (sqlite connection) per request, one lock per repo for writes. Logs hold paths only, never query strings or issue text.
