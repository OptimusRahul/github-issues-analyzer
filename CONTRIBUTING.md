# Contributing

Thanks for helping. Bug reports, docs fixes and code are all welcome.

## Picking an issue

1. Look for issues labeled [`good first issue`](https://github.com/OptimusRahul/github-issues-analyzer/labels/good%20first%20issue) or [`help wanted`](https://github.com/OptimusRahul/github-issues-analyzer/labels/help%20wanted).
2. Comment on the issue to say you want to work on it. Wait until the maintainer assigns it to you, so two people do not do the same work.
3. If you have not opened a pull request within two weeks, the issue may be given to someone else. Comment if you need more time.

For a larger change that has no issue yet, open one first so the approach can be agreed before you write code.

## Setup

You need Python 3.10 or newer and [uv](https://github.com/astral-sh/uv).

```bash
uv sync                          # install dependencies, including test tools
uv sync --extra local            # optional: local embedding model (fastembed)
uv run triage -R owner/repo sync # try the CLI; set GITHUB_TOKEN for a higher rate limit
```

## Tests and lint

CI runs both of these on every pull request. Run them before you push.

```bash
uv run pytest tests/triage
uvx ruff check triage tests
```

Tests use fakes and never call GitHub or a model API, so they need no keys. New behavior needs a test; a bug fix needs a test that fails without the fix.

## Project layout

- `triage/`: the issue triage engine and CLI. Most work happens here.
- `tests/triage/`: tests for the engine.
- `action.yml`: the GitHub Action, a wrapper around the CLI. Docs in `docs/github-action.md`.
- `triage/server.py`, `Dockerfile`, `compose.yaml`: the HTTP server. Docs in `docs/server.md`.
- `docs/superpowers/specs/`: the design spec. Read it before changing how a feature works.

## Pull requests

- Branch from `master` and keep each pull request to one change.
- Write `Closes #123` in the description to link the issue.
- Keep the style of the code around you. Ruff settings are in `pyproject.toml`.
- Update the docs when you change a command, an option or the action.
- The maintainer squash-merges, so the pull request title becomes the commit message. Make it a short sentence in the imperative mood, for example "Add --since to search".

## Code of conduct

Everyone taking part is expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md). Report security problems as described in [SECURITY.md](SECURITY.md), not in a public issue.
