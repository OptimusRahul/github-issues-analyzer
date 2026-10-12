# Duplicate benchmark: neovim/neovim

- Embedding model: `local:BAAI/bge-small-en-v1.5`
- Duplicate pairs: 361
- Non-duplicate sample: 500
- Recall@3 with no threshold: 35%
- Recommended threshold: **0.90** (recall@3 10%, false flags 7%)

| Threshold | Recall@3 | False flags |
|---|---|---|
| 0.50 | 35% | 100% |
| 0.55 | 35% | 100% |
| 0.60 | 35% | 100% |
| 0.65 | 35% | 100% |
| 0.70 | 35% | 99% |
| 0.75 | 34% | 95% |
| 0.80 | 33% | 83% |
| 0.85 | 27% | 42% |
| 0.90 | 10% | 7% |
| 0.95 | 0% | 1% |
