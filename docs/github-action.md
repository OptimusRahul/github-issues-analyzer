# Issue triage as a GitHub Action

Add one workflow file to your repository. The action flags likely duplicates when an issue is opened and posts a weekly digest. It uses the workflow's own token and a local embedding model, so it needs no API key. It starts in dry run: results go to the run's job summary until you set `dry_run: false`.

## Workflow

`.github/workflows/issue-triage.yml`:

```yaml
name: Issue triage

on:
  issues:
    types: [opened]
  schedule:
    - cron: "0 8 * * 1"   # digest every Monday 08:00 UTC
  workflow_dispatch:

permissions:
  issues: write      # comment, label and open the digest issue
  contents: read

concurrency:
  group: issue-triage  # one run at a time, so the cached index is never written twice
  cancel-in-progress: false

jobs:
  triage:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4   # only needed to read .github/issue-triage.yml
      - uses: OptimusRahul/github-issues-analyzer@master
        with:
          command: ${{ github.event_name == 'issues' && 'dupes' || 'digest' }}
          # llm-api-key: ${{ secrets.TRIAGE_LLM_KEY }}   # optional, for models.llm
```

## Configuration

Optional `.github/issue-triage.yml`:

```yaml
dry_run: true              # set to false to post comments, labels and the digest issue
duplicates:
  threshold: 0.86          # run `triage bench` locally to get the value for your repo
  label: possible-duplicate
digest:
  target: issue            # issue | none
  window_days: 7
  waiting_days: 14
models:
  embeddings: { provider: local }
  llm: { base_url: https://api.openai.com/v1, model: your-model-name, api_key_env: TRIAGE_LLM_KEY }
```

## How it works

- The index of your issues lives in the Actions cache. Each run restores the latest copy, syncs only what changed, and saves a new copy. If the cache was evicted (unused for 7 days), the run rebuilds it; with local embeddings this only costs time.
- The embedding model (about 130 MB) is cached alongside the index.
- The action only ever comments on the issue being checked, updates its own earlier comment, adds the configured label, and opens the digest issue. It never closes, edits, locks or assigns issues.
