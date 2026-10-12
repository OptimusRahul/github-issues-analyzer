# Duplicate benchmark: python-poetry/poetry

- Embedding model: `local:BAAI/bge-small-en-v1.5`
- Duplicate pairs: 94
- Non-duplicate sample: 500
- Recall@3 with no threshold: 27%
- Recommended threshold: **0.93** (recall@3 3%, false flags 6%)

| Threshold | Recall@3 | False flags |
|---|---|---|
| 0.50 | 27% | 100% |
| 0.55 | 27% | 100% |
| 0.60 | 27% | 100% |
| 0.65 | 27% | 100% |
| 0.70 | 27% | 99% |
| 0.75 | 27% | 99% |
| 0.80 | 27% | 96% |
| 0.85 | 27% | 83% |
| 0.90 | 10% | 35% |
| 0.93 | 3% | 6% |
| 0.95 | 1% | 1% |
