"""Evaluation runner: execute query set, compute metrics, save results."""

import json
import sys
import time
from pathlib import Path

# Add src/ to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import COLLECTION_NAME, VECTOR_STORE_DIR
from eval.metrics import (
    check_evidence_missing_handling,
    check_groundedness,
    compute_citation_validity,
)
from ingest.embed import get_collection, load_embedder
from rag.pipeline import run_query

EVAL_DIR = Path(__file__).resolve().parent


def evaluate():
    """Run all evaluation queries and compute metrics."""
    print("=" * 60)
    print("RAG Evaluation Runner")
    print("=" * 60)

    # Load query set
    queries_path = EVAL_DIR / "queries.json"
    with open(queries_path) as f:
        queries = json.load(f)
    print(f"Loaded {len(queries)} evaluation queries")

    # Get all valid chunk IDs from ChromaDB
    _client, collection = get_collection()
    all_ids = set(collection.get()["ids"])
    print(f"Vector store has {len(all_ids)} chunks")

    # Load embedder once for all queries
    embedder = load_embedder()

    # Run each query
    results = []
    total_start = time.time()

    for i, q in enumerate(queries, 1):
        qid = q["id"]
        qtype = q["type"]
        query_text = q["query"]
        expected = q.get("expected_sources", [])

        print(f"\n[{i}/{len(queries)}] ({qtype}) {qid}: {query_text[:80]}...")

        try:
            result = run_query(
                query_text=query_text,
                collection=collection,
                embedder=embedder,
            )

            answer = result["answer"]
            chunks = result["retrieved_chunks"]

            # Compute metrics
            citation_valid = compute_citation_validity(answer, all_ids)
            groundedness = check_groundedness(answer, chunks)
            evidence_handling = check_evidence_missing_handling(answer, expected)

            # Check if expected sources appear in retrieved chunks
            retrieved_sources = {c["source_id"] for c in chunks}
            expected_hit = [s for s in expected if s in retrieved_sources]
            source_recall = len(expected_hit) / len(expected) if expected else None

            eval_result = {
                "query_id": qid,
                "query_type": qtype,
                "query_text": query_text,
                "answer": answer,
                "latency_ms": result["latency_ms"],
                "num_chunks_retrieved": len(chunks),
                "retrieved_sources": list(retrieved_sources),
                "expected_sources": expected,
                "source_recall": source_recall,
                "citation_validity": citation_valid,
                "groundedness": groundedness,
                "evidence_handling": evidence_handling,
            }
            results.append(eval_result)

            print(
                f"  Chunks: {len(chunks)} | Citations: {citation_valid['total_citations']} "
                f"(valid: {citation_valid['valid_citations']}) | "
                f"Grounded: {groundedness['groundedness_score']:.0%} | "
                f"Latency: {result['latency_ms']:.0f}ms"
            )
            if source_recall is not None:
                print(f"  Source recall: {source_recall:.0%} ({expected_hit}/{expected})")

        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({
                "query_id": qid,
                "query_type": qtype,
                "query_text": query_text,
                "error": str(e),
            })

    total_time = time.time() - total_start

    # Aggregate metrics
    successful = [r for r in results if "error" not in r]
    print("\n" + "=" * 60)
    print("Evaluation Summary")
    print("=" * 60)
    print(f"Total queries:    {len(queries)}")
    print(f"Successful:       {len(successful)}")
    print(f"Failed:           {len(queries) - len(successful)}")
    print(f"Total time:       {total_time:.1f}s")

    avg_citation_precision = None
    avg_groundedness = None
    avg_source_recall = None

    if successful:
        avg_citation_precision = (
            sum(r["citation_validity"]["citation_precision"] for r in successful) / len(successful)
        )
        avg_groundedness = (
            sum(r["groundedness"]["groundedness_score"] for r in successful) / len(successful)
        )

        with_expected = [r for r in successful if r["source_recall"] is not None]
        avg_source_recall = (
            sum(r["source_recall"] for r in with_expected) / len(with_expected)
            if with_expected
            else None
        )

        edge_cases = [r for r in successful if r["query_type"] == "edge_case"]
        should_flag = [r for r in edge_cases if r["evidence_handling"]["should_flag_missing"]]
        correctly_flagged = [r for r in should_flag if r["evidence_handling"]["correctly_flags_missing"]]

        print(f"\nCitation Metrics:")
        print(f"  Avg citation precision: {avg_citation_precision:.2%}")
        print(f"  Avg groundedness:       {avg_groundedness:.2%}")
        if avg_source_recall is not None:
            print(f"  Avg source recall:      {avg_source_recall:.2%}")
        if should_flag:
            print(f"\nEvidence Missing Detection:")
            print(f"  Should flag missing:    {len(should_flag)}")
            print(f"  Correctly flagged:      {len(correctly_flagged)}")

        for qtype in ["direct", "synthesis", "edge_case"]:
            typed = [r for r in successful if r["query_type"] == qtype]
            if typed:
                avg_cp = sum(r["citation_validity"]["citation_precision"] for r in typed) / len(typed)
                avg_g = sum(r["groundedness"]["groundedness_score"] for r in typed) / len(typed)
                avg_lat = sum(r["latency_ms"] for r in typed) / len(typed)
                print(
                    f"\n  {qtype:12s}: n={len(typed)}, citation_prec={avg_cp:.2%}, "
                    f"groundedness={avg_g:.2%}, avg_latency={avg_lat:.0f}ms"
                )

    # Save results
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    output_path = EVAL_DIR / "eval_results.json"
    with open(output_path, "w") as f:
        json.dump(
            {
                "run_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "total_queries": len(queries),
                "successful": len(successful),
                "total_time_s": round(total_time, 1),
                "aggregate_metrics": {
                    "avg_citation_precision": round(avg_citation_precision, 4) if avg_citation_precision is not None else None,
                    "avg_groundedness": round(avg_groundedness, 4) if avg_groundedness is not None else None,
                    "avg_source_recall": round(avg_source_recall, 4) if avg_source_recall is not None else None,
                },
                "results": results,
            },
            f,
            indent=2,
        )
    print(f"\nResults saved to: {output_path}")

    return {
        "total_queries": len(queries),
        "successful": len(successful),
        "total_time_s": round(total_time, 1),
        "avg_citation_precision": avg_citation_precision,
        "avg_groundedness": avg_groundedness,
        "avg_source_recall": avg_source_recall,
        "results": results,
    }


if __name__ == "__main__":
    evaluate()
