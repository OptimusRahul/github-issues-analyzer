# Duplicate benchmark: microsoft/terminal

- Embedding model: `local:BAAI/bge-small-en-v1.5`
- Duplicate pairs: 437
- Non-duplicate sample: 500
- Recall@3 with no threshold: 27%
- Recommended threshold: **0.92** (recall@3 2%, false flags 8%)

| Threshold | Recall@3 | False flags |
|---|---|---|
| 0.50 | 27% | 100% |
| 0.55 | 27% | 100% |
| 0.60 | 27% | 100% |
| 0.65 | 27% | 100% |
| 0.70 | 27% | 99% |
| 0.75 | 27% | 94% |
| 0.80 | 21% | 75% |
| 0.85 | 11% | 42% |
| 0.90 | 3% | 15% |
| 0.92 | 2% | 8% |
| 0.95 | 1% | 2% |
