# Duplicate benchmark: python-poetry/poetry

- Embedding model: `local:BAAI/bge-small-en-v1.5`
- Duplicate pairs: 94
- Non-duplicate sample: 100
- Recall@3 with no threshold: 27%
- Recommended threshold: **0.93** (recall@3 3%, false flags 8%)

| Threshold | Recall@3 | False flags |
|---|---|---|
| 0.50 | 27% | 100% |
| 0.55 | 27% | 100% |
| 0.60 | 27% | 100% |
| 0.65 | 27% | 100% |
| 0.70 | 27% | 99% |
| 0.75 | 27% | 98% |
| 0.80 | 27% | 96% |
| 0.85 | 27% | 81% |
| 0.90 | 10% | 33% |
| 0.93 | 3% | 8% |
| 0.95 | 1% | 2% |

## With LLM confirmation at 0.80

- Pairs checked: 94, recall@3: 23%
- Non-duplicates checked: 100, false flags: 28%
- LLM calls: 190
