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
labels:
  enabled: false           # suggest labels and a priority for new issues (command: labels)
  apply: false             # true adds the suggested labels; otherwise they are only listed in a comment
  max_labels: 3
models:
  embeddings: { provider: local }
  llm: { base_url: https://api.openai.com/v1, model: your-model-name, api_key_env: TRIAGE_LLM_KEY }
```

## Label suggestions

With `labels.enabled: true`, `command: labels` suggests up to `max_labels` of your repository's existing labels for the new issue, from the labels on its most similar earlier issues (or picked by `models.labels` / `models.llm` when set), plus a priority (high, medium or low) from its reactions and how many similar issues were opened in the last 30 days. Run it as a second step on `issues: opened`:

```yaml
      - uses: OptimusRahul/github-issues-analyzer@master
        if: github.event_name == 'issues'
        with:
          command: labels
```

Measure it on your repository first with `triage bench --labels`: it replays labelled issues and reports precision and recall against the labels maintainers applied. On astral-sh/uv (local embeddings, default settings) it scored 43% precision and 35% recall, so labels are listed, not applied, by default.

## Models

Every model is an OpenAI-compatible endpoint: OpenAI, Ollama, vLLM, llama.cpp server or a hosted open-weight provider. `models.llm` is the default for every task. Set `models.confirm` (duplicate confirmation), `models.ask` or `models.themes` (digest theme names) to use a different model for one task.

```yaml
models:
  embeddings: { provider: openai, model: text-embedding-3-small, price: 0.02 }  # price: USD per 1M tokens
  llm:                                  # cheap open model for confirmation and theme names
    base_url: http://localhost:11434/v1
    model: qwen2.5:7b
    api_key_env: TRIAGE_LLM_KEY
  ask:                                  # a stronger model only for answers
    base_url: https://api.openai.com/v1
    model: your-model-name
    api_key_env: OPENAI_API_KEY
    input_price: 2.5                    # USD per 1M prompt tokens, for the usage report
    output_price: 10
    fallback: { base_url: http://localhost:11434/v1, model: qwen2.5:7b }
```

- If a server rejects JSON mode (`response_format`), the request is repeated without it and the JSON object is read from the reply.
- If a model is unreachable or returns invalid JSON twice, its `fallback` is tried. Both count toward `limits.max_llm_calls_per_run`.
- Each command prints the calls, tokens and cost per model and task.
- Changing the embedding model re-embeds every issue on the next run; vectors from different models are never compared.

### Everything on your own machine

Run [Ollama](https://ollama.com), pull a chat model (`ollama pull qwen2.5:7b`), and point `models.llm` at `http://localhost:11434/v1` as above. Keep `embeddings: { provider: local }` (needs `uv sync --extra local`). No API key or paid service is needed. Run `triage bench --llm` to check a model on your repository before you enable it.

## How it works

- The index of your issues lives in the Actions cache. Each run restores the latest copy, syncs only what changed, and saves a new copy. If the cache was evicted (unused for 7 days), the run rebuilds it; with local embeddings this only costs time.
- The embedding model (about 130 MB) is cached alongside the index.
- The action only ever comments on the issue being checked, updates its own earlier comment, adds the configured label, and opens the digest issue. It never closes, edits, locks or assigns issues.
