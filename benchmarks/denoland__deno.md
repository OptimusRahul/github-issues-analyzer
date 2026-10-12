# Duplicate benchmark: denoland/deno

- Embedding model: `local:BAAI/bge-small-en-v1.5`
- Duplicate pairs: 164
- Non-duplicate sample: 500
- Recall@3 with no threshold: 52%
- Recommended threshold: **0.90** (recall@3 9%, false flags 10%)

| Threshold | Recall@3 | False flags |
|---|---|---|
| 0.50 | 52% | 100% |
| 0.55 | 52% | 100% |
| 0.60 | 52% | 100% |
| 0.65 | 52% | 100% |
| 0.70 | 52% | 99% |
| 0.75 | 51% | 97% |
| 0.80 | 49% | 82% |
| 0.85 | 31% | 45% |
| 0.90 | 9% | 10% |
| 0.95 | 0% | 1% |
