# Duplicate benchmark: astral-sh/uv

- Embedding model: `openai:text-embedding-3-small`
- Duplicate pairs: 181
- Non-duplicate sample: 500
- Recall@3 with no threshold: 48%
- Recommended threshold: **0.79** (recall@3 8%, false flags 8%)

| Threshold | Recall@3 | False flags |
|---|---|---|
| 0.50 | 47% | 97% |
| 0.55 | 46% | 94% |
| 0.60 | 45% | 89% |
| 0.65 | 41% | 78% |
| 0.70 | 34% | 56% |
| 0.75 | 19% | 27% |
| 0.79 | 8% | 8% |
| 0.80 | 7% | 7% |
| 0.85 | 0% | 1% |
| 0.90 | 0% | 0% |
| 0.95 | 0% | 0% |
