#!/usr/bin/env python3
"""
Query pipeline: retrieve relevant chunks → generate cited answer via Ollama.
Includes metadata filtering, trust behavior, and JSONL logging.
"""

import argparse
import json
import re
import time
import uuid
from datetime import datetime, timezone

import chromadb
import ollama
from sentence_transformers import SentenceTransformer

from config import (
    COLLECTION_NAME,
    EMBEDDING_MODEL,
    LOGS_DIR,
    OLLAMA_MODEL,
    PROMPT_TEMPLATE_VERSION,
    RUN_LOG_PATH,
    TOP_K,
    VECTOR_STORE_DIR,
)

# ── Prompt template ───────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are a research assistant answering questions about LLM safety and jailbreaking research.

STRICT RULES:
1. ONLY use information from the provided context chunks. Do NOT use prior knowledge.
2. For EVERY claim you make, cite the source using the format [source_id, chunk_id].
3. If the context does not contain sufficient evidence to answer, respond with:
   "EVIDENCE MISSING: The corpus does not contain sufficient evidence to answer this question."
4. If evidence is conflicting across sources, explicitly flag the conflict.
5. Do NOT invent or fabricate any citations. Only cite chunk IDs that appear in the context below.
6. Answer in a clear, concise manner."""

CONTEXT_TEMPLATE = """\
Context chunks (use these to answer):
{chunks}

Question: {query}"""


def format_chunk_for_prompt(chunk_id: str, source_id: str, title: str, text: str) -> str:
    """Format a single chunk for inclusion in the prompt."""
    return f"[{source_id}, {chunk_id}] (from: {title})\n{text}"


# ── Retrieval ─────────────────────────────────────────────────────────


def retrieve(
    collection,
    embedder: SentenceTransformer,
    query: str,
    top_k: int = TOP_K,
    year: int | None = None,
    author: str | None = None,
    doc_type: str | None = None,
) -> list[dict]:
    """
    Retrieve top-k chunks from ChromaDB with optional metadata filters.
    Returns list of dicts with keys: chunk_id, source_id, title, text, score, section_title.
    """
    # Build where clause for metadata filtering
    where_conditions = []
    if year is not None:
        where_conditions.append({"year": {"$eq": year}})
    if author is not None:
        # ChromaDB $contains doesn't do substring matching on strings.
        # Pre-filter: find all source_ids whose authors field includes the name,
        # then filter with $in on source_id.
        all_meta = collection.get(include=["metadatas"])
        matching_sources = list({
            m["source_id"]
            for m in all_meta["metadatas"]
            if author.lower() in m.get("authors", "").lower()
        })
        if matching_sources:
            where_conditions.append({"source_id": {"$in": matching_sources}})
        else:
            # No papers match this author — return empty
            return []
    if doc_type is not None:
        where_conditions.append({"type": {"$eq": doc_type}})

    where = None
    if len(where_conditions) == 1:
        where = where_conditions[0]
    elif len(where_conditions) > 1:
        where = {"$and": where_conditions}

    # Embed query
    query_embedding = embedder.encode(query).tolist()

    # Query ChromaDB
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    # Parse results
    chunks = []
    if results["ids"] and results["ids"][0]:
        for i, chunk_id in enumerate(results["ids"][0]):
            meta = results["metadatas"][0][i]
            chunks.append({
                "chunk_id": chunk_id,
                "source_id": meta.get("source_id", ""),
                "title": meta.get("title", ""),
                "section_title": meta.get("section_title", ""),
                "text": results["documents"][0][i],
                "distance": results["distances"][0][i],
            })

    return chunks


# ── Generation ────────────────────────────────────────────────────────


def generate_answer(query: str, chunks: list[dict], model: str = OLLAMA_MODEL) -> str:
    """Generate an answer using Ollama with retrieved context."""
    if not chunks:
        return "EVIDENCE MISSING: The corpus does not contain sufficient evidence to answer this question."

    # Format chunks for prompt
    chunk_texts = []
    for c in chunks:
        chunk_texts.append(
            format_chunk_for_prompt(c["chunk_id"], c["source_id"], c["title"], c["text"])
        )
    chunks_str = "\n\n---\n\n".join(chunk_texts)

    user_message = CONTEXT_TEMPLATE.format(chunks=chunks_str, query=query)

    response = ollama.chat(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        options={"num_ctx": 8192},
        think=False,
    )

    content = response["message"]["content"]
    # Strip any residual <think> tags from reasoning models
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
    return content


# ── Logging ───────────────────────────────────────────────────────────


def log_interaction(
    query_text: str,
    metadata_filters: dict,
    retrieved_chunks: list[dict],
    generated_answer: str,
    latency_ms: float,
    model_id: str = OLLAMA_MODEL,
):
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


# ── CLI entry point ───────────────────────────────────────────────────


def run_query(
    query_text: str,
    year: int | None = None,
    author: str | None = None,
    doc_type: str | None = None,
    top_k: int = TOP_K,
    model: str = OLLAMA_MODEL,
) -> dict:
    """
    Run a full query through the pipeline: retrieve → generate → log.
    Returns dict with answer, chunks, and query_id.
    """
    # Load components
    client = chromadb.PersistentClient(path=str(VECTOR_STORE_DIR))
    collection = client.get_collection(name=COLLECTION_NAME)
    embedder = SentenceTransformer(EMBEDDING_MODEL)

    # Build metadata filter dict for logging
    filters = {}
    if year is not None:
        filters["year"] = year
    if author is not None:
        filters["author"] = author
    if doc_type is not None:
        filters["type"] = doc_type

    # Retrieve
    t0 = time.time()
    chunks = retrieve(collection, embedder, query_text, top_k, year, author, doc_type)

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
    parser.add_argument("--top-k", type=int, default=TOP_K, help=f"Number of chunks to retrieve (default {TOP_K})")
    parser.add_argument("--model", default=OLLAMA_MODEL, help=f"Ollama model (default {OLLAMA_MODEL})")
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
        print(f"  [{c['source_id']}, {c['chunk_id']}] dist={c['distance']:.4f} — {c['section_title']}")
    print(f"\n{'='*60}")
    print(f"Answer:\n{result['answer']}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
