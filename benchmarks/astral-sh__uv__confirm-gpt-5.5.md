# Duplicate benchmark: astral-sh/uv

- Embedding model: `local:BAAI/bge-small-en-v1.5`
- Duplicate pairs: 100
- Non-duplicate sample: 100
- Recall@3 with no threshold: 42%
- Recommended threshold: **0.89** (recall@3 7%, false flags 10%)

| Threshold | Recall@3 | False flags |
|---|---|---|
| 0.50 | 42% | 100% |
| 0.55 | 42% | 100% |
| 0.60 | 42% | 100% |
| 0.65 | 42% | 100% |
| 0.70 | 42% | 99% |
| 0.75 | 42% | 97% |
| 0.80 | 38% | 87% |
| 0.85 | 24% | 44% |
| 0.89 | 7% | 10% |
| 0.90 | 4% | 8% |
| 0.95 | 0% | 0% |

## With LLM confirmation at 0.80

- Pairs checked: 100, recall@3: 37%
- Non-duplicates checked: 100, false flags: 24%
- LLM calls: 181
