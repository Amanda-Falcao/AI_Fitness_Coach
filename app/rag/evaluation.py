"""Small deterministic retrieval evaluation harness for a reviewed evidence set."""

import argparse
import json
import statistics
import time
from pathlib import Path
from typing import Callable, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CASES = PROJECT_ROOT / "evaluation" / "retrieval_cases.json"


def evaluate_retrieval(
    cases: Sequence[dict[str, str]],
    retrieve: Callable[[str], Sequence[object]],
    *,
    k: int = 3,
) -> dict[str, float | int]:
    """Compute hit rate, MRR, and mean per-query latency for exact evidence targets.

    Evidence matching is deterministic and case-insensitive. It is a lightweight
    regression signal, not a semantic relevance or answer-faithfulness judge.
    """
    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        raise ValueError("k must be a positive integer")
    if not cases:
        raise ValueError("at least one evaluation case is required")

    reciprocal_ranks: list[float] = []
    latencies_ms: list[float] = []
    for index, case in enumerate(cases):
        query = case.get("query", "").strip()
        evidence = case.get("expected_evidence", "").strip().casefold()
        if not query or not evidence:
            raise ValueError(f"evaluation case {index} requires query and expected_evidence")

        start = time.perf_counter()
        documents = retrieve(query)[:k]
        latencies_ms.append((time.perf_counter() - start) * 1000)
        rank = next(
            (
                position
                for position, document in enumerate(documents, start=1)
                if evidence in getattr(document, "page_content", "").casefold()
            ),
            None,
        )
        reciprocal_ranks.append(1 / rank if rank else 0.0)

    return {
        f"hit_rate_at_{k}": sum(rank > 0 for rank in reciprocal_ranks) / len(cases),
        "mrr": sum(reciprocal_ranks) / len(cases),
        "mean_latency_ms": statistics.mean(latencies_ms),
        "query_count": len(cases),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate retrieval against a reviewed evidence set.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--k", type=int, default=3)
    args = parser.parse_args()
    cases = json.loads(args.cases.read_text(encoding="utf-8"))

    from app.config.settings import Settings
    from app.rag.retriever import create_fitness_retriever

    settings = Settings.from_env()
    retriever = create_fitness_retriever(
        persist_directory=settings.chroma_persist_directory,
        embedding_model_name=settings.embedding_model_name,
        k=args.k,
    )
    results = evaluate_retrieval(cases, retriever.invoke, k=args.k)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
