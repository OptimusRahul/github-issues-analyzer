# Duplicate benchmark: astral-sh/uv

- Embedding model: `local:BAAI/bge-small-en-v1.5`
- Duplicate pairs: 181
- Non-duplicate sample: 500
- Recall@3 with no threshold: 42%
- Recommended threshold: **0.90** (recall@3 5%, false flags 8%)

| Threshold | Recall@3 | False flags |
|---|---|---|
| 0.50 | 42% | 100% |
| 0.55 | 42% | 100% |
| 0.60 | 42% | 100% |
| 0.65 | 42% | 100% |
| 0.70 | 42% | 99% |
| 0.75 | 42% | 95% |
| 0.80 | 39% | 85% |
| 0.85 | 25% | 47% |
| 0.90 | 5% | 8% |
| 0.95 | 0% | 1% |
