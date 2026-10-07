# Issue Triage: Product Design

**Status:** Draft for review
**Date:** 2026-10-06
**Supersedes:** `docs/superpowers/plans/2026-10-06-ecosystem-mvp.md` (ecosystem MVP) and the contributor-finder direction.

## 1. Summary

Open source AI triage for GitHub issues that runs in the maintainer's own repo, on their own keys. It flags likely duplicates when an issue is opened, posts a weekly digest of themes and issues that need attention, and answers questions about the tracker with cited issues.

One core engine is exposed three ways: a CLI, a GitHub Action and a Docker server.

## 2. Goals

1. **Open source tool (now).** Maintainers install it for free and keep it running because it saves them triage time. The project carries no hosting or model cost.
2. **Portfolio piece (now).** A public, reproducible benchmark shows the engine working at `microsoft/vscode` scale (255k issues), with measured duplicate-detection quality.
3. **Business (later).** Not designed for in this spec. Nothing here should block a hosted offering later, but no billing, accounts or multi-tenancy are built.

## 3. Users

- **Primary:** maintainers of mid-size public repos, roughly 500 to 20,000 issues. Usually volunteers without triage staff. Too many issues to read, too few to justify building their own tooling.
- **Secondary:** readers of the benchmark (employers, other maintainers) who want evidence that it works at scale.
- **Not targeted:** very small repos (they can read their issues) and very large repos with dedicated triage teams, except as benchmark subjects.

## 4. Decisions from the review

The LLM council review (2026-10-06) changed the direction:

- Drop the contributor finder and the two-sided ecosystem for now.
- Triage happens in the issue stream, so the product posts duplicate flags and digests where maintainers already work. Chat-style questions remain, but as a secondary feature.
- Prove value with real data (historical duplicates) and a two-week maintainer test before building more.
- Users bring their own keys; the project pays for nothing at runtime.

## 5. Features (v1)

### 5.1 Duplicate flags

- **Trigger:** issue opened (Action, server webhook) or `triage dupes <number>` (CLI).
- **Candidates:** open issues plus issues closed in the last 180 days, excluding the issue itself and pull requests.
- **Method:** embed the issue's title and the start of its body; take the nearest neighbours by cosine similarity; keep those above a similarity threshold (default set from the benchmark). If an LLM is configured, it confirms each candidate and writes a one-line reason; candidates it rejects are dropped.
- **Output:** one comment listing up to 3 candidates (`#number`, title, reason), and optionally a configurable label (default `possible-duplicate`). If nothing passes the threshold, nothing is posted.
- **Never:** closes, edits, locks or assigns issues.
- **Idempotent:** if the issue is edited and re-checked, the tool updates its own earlier comment rather than posting a new one.

### 5.2 Weekly digest

- **Trigger:** schedule (Action cron, server scheduler) or `triage digest` (CLI).
- **Sections:**
  1. **New themes:** clusters where most issues were opened in the last 7 days.
  2. **Growing themes:** clusters whose count of new issues rose compared with the previous digest.
  3. **Most-wanted, no maintainer reply:** highest reaction counts among open issues with no comment from an owner, member or collaborator.
  4. **Waiting on maintainers:** open issues whose latest comment is from a non-maintainer and is older than N days (default 14).
  5. **Likely duplicates still open:** pairs found by duplicate detection that are both still open.
- **Theme names:** written by the LLM if configured, otherwise the top keywords of the cluster.
- **Output:** a new issue (default) or discussion titled `Triage digest – YYYY-MM-DD`, or Markdown to stdout or a file. Every item links to its issues.

### 5.3 Ask

- **Trigger:** `triage ask "<question>"` (CLI) or the server UI. Not available in the Action.
- **Method:** combined search (vector similarity plus full-text keyword search, merged by reciprocal rank fusion), top results passed to the LLM, structured answer with citations. Citations not in the retrieved set are dropped.
- **Requires** an LLM to be configured.

### 5.4 Later (not v1)

- Label suggestions from the repo's own labels.
- "Needs more info" detection (missing reproduction steps or versions).
- **Ready for contributors:** maintainers mark issues they want help with, and the tool checks they are well scoped. This is the planned route back to the contributor finder, because maintainers choose which issues are offered.

## 6. How it runs

```
               core engine (Python package `triage`)
     sync · index · dupes · themes · digest · ask · config
        │                    │                     │
       CLI              GitHub Action         Docker server
   (base layer)        (wraps the CLI)      (FastAPI + web UI,
                                              webhooks, scheduler)
```

| Surface | Who it suits | Ships |
|---|---|---|
| **CLI** `triage` | Trying it out, local runs, the benchmark | First |
| **GitHub Action** | Most maintainers: one workflow file, runs on `issues: opened` and a weekly cron | Second |
| **Docker server** | Maintainers who want the browse-and-ask UI and webhook-driven runs | Third |

All three use the same engine, configuration and index format.

**CLI commands** (the repo comes from `-R owner/repo` or `$GITHUB_REPOSITORY`):
- `triage sync`
- `triage dupes <number>`
- `triage bench`
- `triage digest` (v0.2)
- `triage ask "<question>"` (v0.2)

## 7. Core engine

### 7.1 Sync
- GitHub REST API, 100 items per page, incremental with `since=` the last sync time.
- Pulls all issues (pull requests skipped), and comments from the repo-wide comments endpoint for the last `comments_window_days` (default 180). The benchmark fetches comments of older duplicate issues on demand.
- Saves a checkpoint after every page so an interrupted sync resumes.
- Waits on rate limits using GitHub's reset headers; never fails a run only because of rate limiting if the job time limit allows waiting.
- Resolves the repo's canonical name (follows renames).

### 7.2 Index
- One SQLite file per repo holds issues, comments, embeddings (stored as binary vectors), cluster assignments, posted-comment records and sync state.
- Keyword search uses SQLite's built-in FTS5.
- Vector search is exact (brute force) cosine similarity in NumPy. For 20k issues at 512 dimensions this is about 40 MB in memory and takes milliseconds; at vscode scale (255k) it is about 500 MB and still under a second. No separate vector database.
- Only new or changed issues are re-embedded (content hash).

### 7.3 Models
- **Embeddings:** any OpenAI-compatible endpoint, or a local model run in-process (no key needed). The Action defaults to the local model so duplicate flags work with no model key at all.
- **LLM:** any OpenAI-compatible endpoint (OpenAI, Ollama, vLLM, hosted open-weight providers). Optional. Without it, duplicate flags have no written reason, theme names are keywords, and Ask is unavailable.
- Each model is set by `base_url`, `model` and an API key read from an environment variable.

### 7.4 Themes
- Cluster open issues' embeddings (density-based clustering, so unrelated issues are left unclustered rather than forced into a theme).
- Store each issue's cluster and each digest's cluster counts so the next digest can compare.

## 8. Configuration

A file at `.github/issue-triage.yml`, also used by the CLI and server:

```yaml
dry_run: true              # first run writes to the job summary only
duplicates:
  enabled: true
  threshold: 0.86          # replaced by the benchmark-tuned default
  max_candidates: 3
  label: possible-duplicate
  closed_window_days: 180
digest:
  enabled: true
  target: issue            # issue | discussion | none
  waiting_days: 14
exclude_labels: [wontfix]
models:
  embeddings: { provider: local }
  llm: { base_url: http://localhost:11434/v1, model: your-model-name, api_key_env: TRIAGE_LLM_KEY }  # any OpenAI-compatible endpoint
limits:
  max_llm_calls_per_run: 50
```

## 9. GitHub Action specifics

- **Permissions:** `issues: write`, `contents: read`, and `discussions: write` only when the digest posts to discussions.
- **Index storage:** the SQLite file is kept in the Actions cache. Each run restores the latest cache, syncs changes since the last run, and saves a new cache entry. If the cache was evicted (unused for 7 days), the run rebuilds the index; with local embeddings this costs only time.
- **Concurrent runs:** if two issues open at once, both runs may save a cache and one issue may be missing from the saved index. The next run's incremental sync adds it. Duplicate checks are unaffected because each run checks its own issue.
- **Dry run:** results go to the job summary instead of comments until `dry_run: false`.

## 10. Safety

- Comment and digest text is built from templates. The LLM only fills short fields (reason, theme name), each length-capped, with `@mentions` and links stripped so it cannot ping people or insert links.
- Issue text is passed to the LLM as delimited, untrusted data. The LLM has no tools.
- Cited issue numbers must come from the candidate or retrieved set.
- Cost cap per run (`max_llm_calls_per_run`).
- No secrets in the index; tokens come from the environment only.

## 11. Proving it works

### 11.1 Duplicate benchmark (`triage bench`)
- **Ground truth:** issues closed as duplicates, identified by `state_reason: duplicate` where available, or the `duplicate` label together with a "Duplicate of #N" reference.
- **Replay:** for each duplicate, search only issues created before it, as the tool would have seen them on the day it was filed.
- **Metrics:**
  - **Recall@3:** the original is among the top 3 candidates.
  - **False flag rate:** share of a sample of non-duplicate issues that would have been flagged.
- **Initial targets:** recall@3 of at least 60% and a false flag rate of at most 10%, measured on 5 mid-size repos. Targets are revised after the first run, and the default threshold is set from the results.
- Results are compared for local embeddings vs an API embedding model, and with vs without LLM confirmation.

### 11.2 Scale showcase
Run `sync`, `bench` and `digest` on `microsoft/vscode` and publish the following in the README:
- sync time and API calls used;
- index size;
- query latency;
- benchmark metrics.

### 11.3 Two-week maintainer test
1. Run the CLI on 5 mid-size repos.
2. Send each maintainer a short report listing open issues that look like duplicates, with links.
3. **Go:** 2 or more maintainers act on the report or ask to install it, and the Action gets built.
4. **Stop:** if none do, rethink before building more.

## 12. Success measures

- Benchmark meets the targets in 11.1 on at least 4 of 5 repos.
- 5 repos keep the Action running for 30 days after install.
- In those repos, maintainers act on (close, link or label) at least a quarter of flagged duplicates.

## 13. Out of scope

Hosted service, accounts and GitHub login, billing, multi-tenancy, Slack, the contributor finder, Postgres and pgvector, and auto-closing issues.

## 14. Relationship to existing code

- The current FastAPI app in `src/` becomes the starting point of the Docker server surface (third to ship). Its scan and analyze logic is replaced by the core engine.
- The engine is a new package, `triage`, in this repo. The existing GitHub client and OpenAI wrapper are rewritten inside it (paginated sync, OpenAI-compatible models).
- `open-source-project-finder` is frozen. Its leaked OAuth secret must still be reset.
