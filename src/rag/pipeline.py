"""Full RAG query pipeline: retrieve -> generate -> log."""

import argparse
import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Add src/ to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import (
    LLM_MODEL,
    LOGS_DIR,
    PROMPT_TEMPLATE_VERSION,
    RUN_LOG_PATH,
    TOP_K,
)
from ingest.embed import get_collection, load_embedder
from rag.generate import generate_answer
from rag.retrieve import retrieve_diversified


def log_interaction(
    query_text: str,
    metadata_filters: dict,
    retrieved_chunks: list[dict],
    generated_answer: str,
    latency_ms: float,
    model_id: str = LLM_MODEL,
) -> str:
    """Append a structured log entry to the run log JSONL file."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "query_id": str(uuid.uuid4()),
        "query_text": query_text,
        "metadata_filters": metadata_filters,
        "retrieved_chunks": [
            {
                "chunk_id": c["chunk_id"],
                "source_id": c["source_id"],
                "title": c["title"],
                "section_title": c["section_title"],
                "distance": c["distance"],
                "text_snippet": c["text"][:200],
            }
            for c in retrieved_chunks
        ],
        "prompt_template_version": PROMPT_TEMPLATE_VERSION,
        "model_id": model_id,
        "generated_answer": generated_answer,
        "latency_ms": round(latency_ms, 1),
    }

    with open(RUN_LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")

    return entry["query_id"]


def run_query(
    query_text: str,
    year: int | None = None,
    author: str | None = None,
    doc_type: str | None = None,
    top_k: int = TOP_K,
    model: str = LLM_MODEL,
    collection=None,
    embedder=None,
) -> dict:
    """
    Run a full query through the pipeline: retrieve -> generate -> log.
    Returns dict with answer, chunks, and query_id.
    """
    # Load components if not provided
    if collection is None:
        _client, collection = get_collection()
    if embedder is None:
        embedder = load_embedder()

    # Build metadata filter dict for logging
    filters = {}
    if year is not None:
        filters["year"] = year
    if author is not None:
        filters["author"] = author
    if doc_type is not None:
        filters["type"] = doc_type

    # Retrieve with source diversification
    t0 = time.time()
    chunks = retrieve_diversified(
        collection, embedder, query_text, top_k, year=year, author=author, doc_type=doc_type
    )

    # Generate
    answer = generate_answer(query_text, chunks, model)
    latency_ms = (time.time() - t0) * 1000

    # Log
    query_id = log_interaction(query_text, filters, chunks, answer, latency_ms, model)

    return {
        "query_id": query_id,
        "query_text": query_text,
        "answer": answer,
        "retrieved_chunks": chunks,
        "latency_ms": latency_ms,
    }


def main():
    parser = argparse.ArgumentParser(description="Query the RAG pipeline")
    parser.add_argument("--text", required=True, help="Query text")
    parser.add_argument("--year", type=int, default=None, help="Filter by publication year")
    parser.add_argument("--author", default=None, help="Filter by author name (substring match)")
    parser.add_argument("--type", dest="doc_type", default=None, help="Filter by document type")
    parser.add_argument("--top-k", type=int, default=TOP_K, help=f"Number of chunks (default {TOP_K})")
    parser.add_argument("--model", default=LLM_MODEL, help=f"LLM model (default {LLM_MODEL})")
    args = parser.parse_args()

    result = run_query(
        query_text=args.text,
        year=args.year,
        author=args.author,
        doc_type=args.doc_type,
        top_k=args.top_k,
        model=args.model,
    )

    # Display results
    print(f"\nQuery: {result['query_text']}")
    print(f"Query ID: {result['query_id']}")
    print(f"Latency: {result['latency_ms']:.0f}ms")
    print(f"\nRetrieved {len(result['retrieved_chunks'])} chunks:")
    for c in result["retrieved_chunks"]:
        print(f"  [{c['source_id']}, {c['chunk_id']}] dist={c['distance']:.4f} -- {c['section_title']}")
    print(f"\n{'='*60}")
    print(f"Answer:\n{result['answer']}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
