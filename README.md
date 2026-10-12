# GitHub Issues Analyzer

Open source AI triage for GitHub issues. It runs in your own repository, on your own keys:

- lists related issues when an issue is opened, and flags the ones an LLM confirms as possible duplicates
- posts a weekly digest of themes and issues waiting for a maintainer
- searches issues by keywords and meaning, and answers questions with cited issues

It works with a local embedding model, so no API key is needed for duplicates, search or the digest. It starts in dry run and never closes, edits or assigns issues.

## Use it as a GitHub Action

See [docs/github-action.md](docs/github-action.md) for the workflow file and configuration.

## Use the CLI

Requires Python 3.10+ and [uv](https://github.com/astral-sh/uv).

```bash
uv sync --extra local                     # local embeddings
export GITHUB_TOKEN=...                   # optional, raises the GitHub rate limit
uv run triage -R owner/repo sync          # build the index
uv run triage -R owner/repo dupes 123     # related issues and possible duplicates of #123
uv run triage -R owner/repo search "error text"
uv run triage -R owner/repo digest
uv run triage -R owner/repo ask "why does install fail on Windows?"  # needs models.llm
uv run triage -R owner/repo bench         # measure duplicate detection on past duplicates
```

## Status

Similarity search finds the duplicate among the top 3 related issues 27–52% of the time; a strong LLM then confirms duplicates with few false claims. See [benchmarks/README.md](benchmarks/README.md). The roadmap is in [#36](https://github.com/OptimusRahul/github-issues-analyzer/issues/36).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Licensed under the [MIT License](LICENSE).

## Run the server

A Docker server with a webhook, scheduled sync and digest, and an API for search and Ask: see [docs/server.md](docs/server.md).
