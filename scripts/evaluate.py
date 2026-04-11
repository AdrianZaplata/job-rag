"""RAGAS evaluation script for the Job RAG system.

Runs the full RAG pipeline against a golden query dataset and evaluates
retrieval + generation quality using RAGAS metrics.

Requirements:
    - Running PostgreSQL with pgvector (docker compose up db)
    - Postings ingested and embedded (job-rag ingest && job-rag embed)
    - OPENAI_API_KEY set in .env

Usage:
    uv run python scripts/evaluate.py
"""

import asyncio
import json
import math
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

# Load .env so OPENAI_API_KEY is available to RAGAS
load_dotenv()

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


async def run_evaluation() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not set. Add it to .env or export it.")
        sys.exit(1)

    from openai import AsyncOpenAI
    from ragas.embeddings import OpenAIEmbeddings as RagasOpenAIEmbeddings
    from ragas.llms import llm_factory
    from ragas.metrics.collections import (
        AnswerRelevancy,
        ContextPrecisionWithReference,
        ContextRecall,
        Faithfulness,
    )

    from job_rag.db.engine import AsyncSessionLocal
    from job_rag.logging import get_logger
    from job_rag.services.retrieval import rag_query, rerank, search_postings

    log = get_logger(__name__)

    # Load golden queries
    golden_path = Path("data/eval/golden_queries.json")
    golden_queries = json.loads(golden_path.read_text(encoding="utf-8"))
    log.info("loaded_golden_queries", count=len(golden_queries))

    # Collect RAG results for each query
    query_data: list[dict] = []

    for i, entry in enumerate(golden_queries):
        question = entry["question"]
        ground_truth = entry["ground_truth"]

        log.info("evaluating_query", index=i + 1, question=question[:60])

        async with AsyncSessionLocal() as session:
            result = await rag_query(session, question)
            answer = result["answer"]

            raw_results = await search_postings(session, question, top_k=20)
            reranked = rerank(question, raw_results, top_k=5)

            contexts: list[str] = []
            for r in reranked:
                posting = r["posting"]
                must_have = [req.skill for req in posting.requirements if req.required]
                nice_to_have = [
                    req.skill for req in posting.requirements if not req.required
                ]
                ctx = (
                    f"{posting.title} at {posting.company} "
                    f"({posting.location}, {posting.remote_policy}). "
                    f"Seniority: {posting.seniority}. "
                    f"Must-have: {', '.join(must_have)}. "
                    f"Nice-to-have: {', '.join(nice_to_have)}. "
                    f"Responsibilities: {posting.responsibilities[:300]}"
                )
                contexts.append(ctx)

        query_data.append({
            "question": question,
            "answer": answer,
            "contexts": contexts,
            "ground_truth": ground_truth,
        })

    log.info("all_queries_complete", total=len(query_data))

    # Set up RAGAS LLM and embeddings
    openai_client = AsyncOpenAI()
    eval_llm = llm_factory("gpt-4o-mini", client=openai_client)
    eval_embeddings = RagasOpenAIEmbeddings(
        client=openai_client, model="text-embedding-3-small"
    )

    # Initialize metrics
    faithfulness = Faithfulness(llm=eval_llm)
    answer_relevancy = AnswerRelevancy(llm=eval_llm, embeddings=eval_embeddings)
    context_precision = ContextPrecisionWithReference(llm=eval_llm)
    context_recall = ContextRecall(llm=eval_llm)

    # Score each query individually
    log.info("running_ragas_evaluation")
    per_query_results: list[dict] = []
    agg: dict[str, list[float]] = {
        "faithfulness": [],
        "answer_relevancy": [],
        "context_precision": [],
        "context_recall": [],
    }

    async def _safe_score(name: str, coro):
        try:
            return float(await coro)
        except Exception as e:
            log.warning("metric_failed", metric=name, error=str(e)[:200])
            return float("nan")

    for i, qd in enumerate(query_data):
        log.info("scoring_query", index=i + 1, question=qd["question"][:50])

        scores = {
            "faithfulness": await _safe_score(
                "faithfulness",
                faithfulness.ascore(
                    user_input=qd["question"],
                    response=qd["answer"],
                    retrieved_contexts=qd["contexts"],
                ),
            ),
            "answer_relevancy": await _safe_score(
                "answer_relevancy",
                answer_relevancy.ascore(
                    user_input=qd["question"],
                    response=qd["answer"],
                ),
            ),
            "context_precision": await _safe_score(
                "context_precision",
                context_precision.ascore(
                    user_input=qd["question"],
                    reference=qd["ground_truth"],
                    retrieved_contexts=qd["contexts"],
                ),
            ),
            "context_recall": await _safe_score(
                "context_recall",
                context_recall.ascore(
                    user_input=qd["question"],
                    retrieved_contexts=qd["contexts"],
                    reference=qd["ground_truth"],
                ),
            ),
        }

        for k, v in scores.items():
            if not math.isnan(v):
                agg[k].append(v)

        per_query_results.append({
            "question": qd["question"],
            "answer_length": len(qd["answer"]),
            "num_contexts": len(qd["contexts"]),
            "scores": scores,
        })

    # Compute averages over successful scores only
    avg_scores = {
        k: (sum(v) / len(v) if v else float("nan")) for k, v in agg.items()
    }
    sample_counts = {k: len(v) for k, v in agg.items()}

    # Print results
    print("\n" + "=" * 60)
    print("RAGAS Evaluation Results")
    print("=" * 60)
    for metric_name, score in avg_scores.items():
        n = sample_counts[metric_name]
        print(f"  {metric_name:<25} {score:.4f}  (n={n}/{len(query_data)})")
    print("=" * 60)

    # Save results to file
    output = {
        "timestamp": datetime.now(UTC).isoformat(),
        "num_queries": len(golden_queries),
        "metrics": avg_scores,
        "sample_counts": sample_counts,
        "per_query": per_query_results,
    }

    output_path = Path("data/eval/results.json")
    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    log.info("results_saved", path=str(output_path))
    print(f"\nResults saved to {output_path}")


if __name__ == "__main__":
    asyncio.run(run_evaluation())
