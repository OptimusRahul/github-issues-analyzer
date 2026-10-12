# Duplicate benchmark: python-poetry/poetry

- Embedding model: `openai:text-embedding-3-small`
- Duplicate pairs: 94
- Non-duplicate sample: 500
- Recall@3 with no threshold: 30%
- Recommended threshold: **0.85** (recall@3 2%, false flags 4%)

| Threshold | Recall@3 | False flags |
|---|---|---|
| 0.50 | 30% | 99% |
| 0.55 | 30% | 99% |
| 0.60 | 30% | 97% |
| 0.65 | 30% | 92% |
| 0.70 | 28% | 83% |
| 0.75 | 22% | 64% |
| 0.80 | 13% | 28% |
| 0.85 | 2% | 4% |
| 0.90 | 1% | 1% |
| 0.95 | 1% | 0% |
