# Maintainer test (#40)

Goal: find out whether maintainers of mid-size repositories act on duplicate reports. Go/stop rule from the spec: if at least 2 of 5 maintainers act on a report (close, link or label a pair) or ask to install the tool, keep building; otherwise revisit the product.

## Repositories

The five repositories from the benchmark (2k to 20k issues, with a history of closed duplicates):

| Repository | Issues | Benchmark report |
|---|---|---|
| astral-sh/uv | 9,336 | `benchmarks/astral-sh__uv.md` |
| neovim/neovim | 14,697 | `benchmarks/neovim__neovim.md` |
| denoland/deno | 15,148 | `benchmarks/denoland__deno.md` |
| python-poetry/poetry | 6,363 | `benchmarks/python-poetry__poetry.md` |
| microsoft/terminal | 14,146 | `benchmarks/microsoft__terminal.md` |

## Producing a report

Run after the benchmark has finished for the repository, so the index is complete. Use the threshold the benchmark recommends. Nothing is posted: dry run is the default and `target: none` keeps the digest local.

```bash
cat > /tmp/report.yml <<'YAML'
dry_run: true
duplicates:
  threshold: 0.86        # replace with the recommended threshold from benchmarks/<repo>.md
digest:
  target: none
  window_days: 60        # pairs among issues opened in the last 60 days
YAML
uv run triage -R OWNER/REPO --config /tmp/report.yml digest > reports/OWNER__REPO.md
```

Take the "Likely duplicates still open" section. Open each pair on GitHub and drop any that are clearly not the same problem; keep up to 10 good pairs.

## Message

Send through the channel the project prefers (Discussions, Discord or Zulip, or email for a maintainer who lists one). Do not open an issue or comment on their tracker.

> **Subject:** N open issues in OWNER/REPO that look like duplicates
>
> Hi NAME,
>
> I'm building issue-triage, an open source tool that flags likely duplicate GitHub issues. I ran it on OWNER/REPO's recent open issues. Nothing was posted to your repository. These pairs look like duplicates:
>
> - #A "TITLE A" looks like #B "TITLE B"
> - …
>
> Replayed against issues your team already closed as duplicates, it finds the original in its top 3 suggestions X% of the time, and flags Y% of non-duplicates.
>
> If this is useful, it runs as a GitHub Action that comments on newly opened issues (dry run first, and it never closes anything). I'd be glad to help set it up. If any of these pairs are wrong, telling me why helps too.
>
> Thanks,
> NAME

## Log

| Repository | Sent (date, channel) | Pairs sent | Response | Pairs acted on | Asked to install |
|---|---|---|---|---|---|
| astral-sh/uv | | | | | |
| neovim/neovim | | | | | |
| denoland/deno | | | | | |
| python-poetry/poetry | | | | | |
| microsoft/terminal | | | | | |

Decision after two weeks: copy this table to issue #40 and record go or stop.
