#!/usr/bin/env python3
"""
Evaluation runner: execute query set, compute metrics, save results.

Metrics:
  1. Groundedness / Faithfulness: Do cited chunk IDs exist in the vector store?
  2. Citation Precision: Fraction of citations that resolve to real chunks.
  3. Answer Relevance (heuristic): Does the answer address the query topic?
"""

import json
import re
import sys
import time

import chromadb
from sentence_transformers import SentenceTransformer

from config import (
    COLLECTION_NAME,
    EMBEDDING_MODEL,
    EVAL_DIR,
    OLLAMA_MODEL,
    VECTOR_STORE_DIR,
)
from query import run_query

# ── Citation extraction ───────────────────────────────────────────────


def extract_citations(answer: str) -> list[tuple[str, str]]:
    """
    Extract [source_id, chunk_id] citations from an answer.
    Handles multiple formats the model might use:
      [source_id, chunk_id]
      [source_id, chunk_id]
      [chunk_id] (standalone)
    Returns list of (source_id, chunk_id) tuples.
    """
    # Primary pattern: [source_id, chunk_id]
    pattern = r"\[([a-z0-9_.\- ]+),\s*([a-z0-9_]+_c\d+)\]"
    citations = re.findall(pattern, answer, re.IGNORECASE)

    # Fallback: standalone [chunk_id] references
    if not citations:
        standalone = re.findall(r"\[([a-z0-9_]+_c\d+)\]", answer, re.IGNORECASE)
        citations = [("", cid) for cid in standalone]

    return citations


def extract_chunk_ids(answer: str) -> list[str]:
    """Extract just the chunk_ids from citations."""
    citations = extract_citations(answer)
    return [chunk_id for _, chunk_id in citations]


# ── Metrics ───────────────────────────────────────────────────────────


def compute_citation_validity(answer: str, valid_chunk_ids: set[str]) -> dict:
    """
    Check if cited chunk IDs actually exist in the vector store.
    Returns dict with counts and precision.
    """
    cited_ids = extract_chunk_ids(answer)

    if not cited_ids:
        return {
            "total_citations": 0,
            "valid_citations": 0,
            "invalid_citations": 0,
            "citation_precision": 0.0,
            "cited_ids": [],
            "invalid_ids": [],
        }

    valid = [cid for cid in cited_ids if cid in valid_chunk_ids]
    invalid = [cid for cid in cited_ids if cid not in valid_chunk_ids]

    return {
        "total_citations": len(cited_ids),
        "valid_citations": len(valid),
        "invalid_citations": len(invalid),
        "citation_precision": len(valid) / len(cited_ids) if cited_ids else 0.0,
        "cited_ids": cited_ids,
        "invalid_ids": invalid,
    }


def check_groundedness(answer: str, retrieved_chunks: list[dict]) -> dict:
    """
    Check if the answer's citations match the retrieved chunks.
    A grounded answer only cites chunks that were actually retrieved.
    """
    retrieved_ids = {c["chunk_id"] for c in retrieved_chunks}
    cited_ids = set(extract_chunk_ids(answer))

    if not cited_ids:
        return {
            "is_grounded": False,
            "grounded_citations": 0,
            "ungrounded_citations": 0,
            "groundedness_score": 0.0,
            "note": "No citations found in answer",
        }

    grounded = cited_ids & retrieved_ids
    ungrounded = cited_ids - retrieved_ids

    return {
        "is_grounded": len(ungrounded) == 0,
        "grounded_citations": len(grounded),
        "ungrounded_citations": len(ungrounded),
        "groundedness_score": len(grounded) / len(cited_ids) if cited_ids else 0.0,
        "ungrounded_ids": list(ungrounded),
    }


def check_evidence_missing_handling(answer: str, expected_sources: list[str]) -> dict:
    """
    For edge-case queries with no expected sources, check if the system
    correctly flags missing evidence.
    """
    flags_missing = "evidence missing" in answer.lower() or "not contain" in answer.lower() or "no evidence" in answer.lower() or "insufficient evidence" in answer.lower()

    if not expected_sources:
        return {
            "should_flag_missing": True,
            "correctly_flags_missing": flags_missing,
        }
    return {
        "should_flag_missing": False,
        "correctly_flags_missing": None,
    }


# ── Main evaluation ──────────────────────────────────────────────────


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
    client = chromadb.PersistentClient(path=str(VECTOR_STORE_DIR))
    collection = client.get_collection(name=COLLECTION_NAME)
    all_ids = set(collection.get()["ids"])
    print(f"Vector store has {len(all_ids)} chunks")

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
            result = run_query(query_text=query_text)

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

            # Print summary
            print(f"  Chunks: {len(chunks)} | Citations: {citation_valid['total_citations']} "
                  f"(valid: {citation_valid['valid_citations']}) | "
                  f"Grounded: {groundedness['groundedness_score']:.0%} | "
                  f"Latency: {result['latency_ms']:.0f}ms")
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

    if successful:
        # Citation metrics
        total_citations = sum(r["citation_validity"]["total_citations"] for r in successful)
        valid_citations = sum(r["citation_validity"]["valid_citations"] for r in successful)
        avg_citation_precision = (
            sum(r["citation_validity"]["citation_precision"] for r in successful) / len(successful)
        )

        # Groundedness
        avg_groundedness = (
            sum(r["groundedness"]["groundedness_score"] for r in successful) / len(successful)
        )

        # Source recall (for queries with expected sources)
        with_expected = [r for r in successful if r["source_recall"] is not None]
        avg_source_recall = (
            sum(r["source_recall"] for r in with_expected) / len(with_expected)
            if with_expected else None
        )

        # Evidence handling (for edge cases)
        edge_cases = [r for r in successful if r["query_type"] == "edge_case"]
        should_flag = [r for r in edge_cases if r["evidence_handling"]["should_flag_missing"]]
        correctly_flagged = [r for r in should_flag if r["evidence_handling"]["correctly_flags_missing"]]

        print(f"\nCitation Metrics:")
        print(f"  Total citations:        {total_citations}")
        print(f"  Valid citations:        {valid_citations}")
        print(f"  Avg citation precision: {avg_citation_precision:.2%}")
        print(f"  Avg groundedness:       {avg_groundedness:.2%}")
        if avg_source_recall is not None:
            print(f"  Avg source recall:      {avg_source_recall:.2%}")
        if should_flag:
            print(f"\nEvidence Missing Detection:")
            print(f"  Should flag missing:    {len(should_flag)}")
            print(f"  Correctly flagged:      {len(correctly_flagged)}")

        # Per-type breakdown
        for qtype in ["direct", "synthesis", "edge_case"]:
            typed = [r for r in successful if r["query_type"] == qtype]
            if typed:
                avg_cp = sum(r["citation_validity"]["citation_precision"] for r in typed) / len(typed)
                avg_g = sum(r["groundedness"]["groundedness_score"] for r in typed) / len(typed)
                avg_lat = sum(r["latency_ms"] for r in typed) / len(typed)
                print(f"\n  {qtype:12s}: n={len(typed)}, citation_prec={avg_cp:.2%}, "
                      f"groundedness={avg_g:.2%}, avg_latency={avg_lat:.0f}ms")

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
                    "avg_citation_precision": round(avg_citation_precision, 4) if successful else None,
                    "avg_groundedness": round(avg_groundedness, 4) if successful else None,
                    "avg_source_recall": round(avg_source_recall, 4) if avg_source_recall is not None else None,
                },
                "results": results,
            },
            f,
            indent=2,
        )
    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    evaluate()
