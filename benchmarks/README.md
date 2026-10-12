# Duplicate detection benchmarks

Reports from `triage bench`. Ground truth: issues closed as duplicates ("Duplicate of #N"), each replayed against only the issues created before it. "False flags" counts sampled issues that were never closed as duplicates but got a candidate (or, with an LLM, a confirmed duplicate).

## Retrieval: is the duplicate among the 3 most similar earlier issues?

| Repository | Duplicate pairs | Local `bge-small-en-v1.5` | OpenAI `text-embedding-3-small` |
|---|---|---|---|
| astral-sh/uv | 181 | 42% | 48% |
| python-poetry/poetry | 94 | 27% | 30% |
| denoland/deno | 164 | 52% | |
| neovim/neovim | 361 | 35% | |
| microsoft/terminal | 437 | 27% | |

With similarity alone, no threshold keeps false flags at or below 10% while finding more than 10% of duplicates, on any repository or embedding model. The original target (recall@3 ≥ 60%, false flags ≤ 10%) is out of reach for similarity search: even with no threshold the duplicate is in the top 3 only 27–52% of the time.

## Confirmation by an LLM (candidates from similarity ≥ 0.80, local embeddings)

| Repository | Model | Recall@3 | False flags | Ceiling at 0.80 |
|---|---|---|---|---|
| astral-sh/uv | gpt-5.4-mini (first prompt) | 39% | 79% | 39% |
| astral-sh/uv | gpt-5.4-mini (strict prompt, 200 sampled) | 38% | 62% | 39% |
| astral-sh/uv | gpt-5.5 (100 pairs, 100 sampled) | 37% | 24% | 39% |
| python-poetry/poetry | gpt-5.4-mini (first prompt) | 23% | 89% | 27% |
| python-poetry/poetry | gpt-5.5 (100 sampled) | 23% | 28% | 27% |

The ground truth undercounts duplicates: many open issues duplicate older ones without being closed as such. A hand check of 25 pairs that gpt-5.4-mini confirmed on uv found 9 real duplicates and 16 related-but-different issues. On those same 25 pairs:

| Model | Real duplicates confirmed | Non-duplicates confirmed |
|---|---|---|
| gpt-5.5 | 8 of 9 | 0 of 16 |
| gpt-5.4 | 8 of 9 | 5 of 16 |
| gpt-5.4-mini | 9 of 9 | 12 of 16 |

So the product lists related issues by similarity and only calls a candidate a possible duplicate when a strong model confirms it; small models confirm related issues far too often.
