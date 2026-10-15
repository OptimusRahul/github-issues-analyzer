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

## Scale run: microsoft/vscode

The full issue backfill completed and resumed from its saved comments cursor after GitHub returned one HTTP 500. It indexed 256,158 issues and the 30,000 comments returned for the configured 180-day comment window. The SQLite size below is before embeddings are generated.

| Metric | Result |
|---|---|
| Issues indexed | 256,158 |
| Recent comments indexed | 30,000 (180-day window) |
| Sync time | 1h 34m 19s of active command time across the initial attempt and resume; excludes the pause between attempts |
| GitHub API requests | 3,552 total: 3,250 issue pages, 300 comment pages, one repository lookup, and one failed HTTP 500 request |
| SQLite index size | 834.8 MiB (875,171,840 bytes), before embeddings |
| Embedding and duplicate benchmark | Not measured: the local model download was blocked by repeated connection resets from Hugging Face |
| Duplicate-query latency | Not measured: the index has no embeddings |
| Digest | Not generated: it requires embeddings |

Reproduce the sync, benchmark, query timings, and digest with a GitHub token and network access to download the local embedding model:

```bash
uv sync --extra local
export GITHUB_TOKEN=...  # optional, raises the GitHub API rate limit
uv run triage -R microsoft/vscode sync
uv run triage -R microsoft/vscode bench --max-pairs 1000 --out benchmarks/microsoft__vscode.md
for n in ISSUE1 ISSUE2 ISSUE3 ISSUE4 ISSUE5; do
  /usr/bin/time -f '%e seconds' uv run --no-sync triage -R microsoft/vscode dupes "$n"
done
uv run triage -R microsoft/vscode digest
```

Run the `dupes` timings after the benchmark has populated the embeddings; replace the sample issue numbers with recent open issues. On Windows PowerShell, set the token with `$env:GITHUB_TOKEN = "..."` and time a command with `Measure-Command { uv run --no-sync triage -R microsoft/vscode dupes ISSUE_NUMBER }`. The page count is based on GitHub's 100-item pagination and the repository's issue and pull-request totals; the sync resumed from the saved cursor rather than refetching its completed issue pages.

## Status

Similarity search finds the duplicate among the top 3 related issues 27–52% of the time; a strong LLM then confirms duplicates with few false claims. See [benchmarks/README.md](benchmarks/README.md). The roadmap is in [#36](https://github.com/OptimusRahul/github-issues-analyzer/issues/36).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Licensed under the [MIT License](LICENSE).

## Run the server

A Docker server with a webhook, scheduled sync and digest, and an API for search and Ask: see [docs/server.md](docs/server.md).
