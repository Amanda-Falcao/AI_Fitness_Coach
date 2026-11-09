# Retrieval Evaluation

## Protocol

The benchmark in `evaluation/retrieval_cases.json` contains five manually reviewed query/evidence pairs from the current fitness knowledge text. `python -m app.rag.evaluation` retrieves the top three chunks and checks each expected evidence string using case-insensitive exact substring matching.

- **Hit-rate@3:** fraction of queries with the target evidence in the top three results.
- **Mean reciprocal rank (MRR):** average of `1 / rank` for the first matching result; misses score zero.
- **Mean latency:** average time spent inside each retriever invocation. Embedding model construction and weight loading happen before the timer starts.

## Observed baseline

One real run against the Docker Compose Chroma volume, after ingesting the current source and loading `all-MiniLM-L6-v2`, returned:

| Metric | Observed value |
| --- | ---: |
| Queries | 5 |
| Hit-rate@3 | 1.00 |
| MRR | 0.90 |
| Mean retrieval latency | 7.89 ms |

This is a small prototype baseline, not a general quality or production latency claim. Exact evidence matching does not measure semantic relevance beyond the selected snippets, answer faithfulness, safety, plan usefulness, or LLM generation latency/cost. Latency depends on hardware and warm state.

## Re-run

```bash
docker compose run --rm --entrypoint python fitness-coach -m app.rag.ingestion
docker compose run --rm --entrypoint python fitness-coach -m app.rag.evaluation
```

Expand and review the query set before changing chunk size, overlap, embedding model, or `k`. Keep the previous result when comparing settings so tuning has a reproducible reference.
