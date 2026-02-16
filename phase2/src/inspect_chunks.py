#!/usr/bin/env python3
"""Inspect chunks stored in ChromaDB."""

import argparse
import chromadb
from config import COLLECTION_NAME, VECTOR_STORE_DIR


def main():
    parser = argparse.ArgumentParser(description="Inspect chunks in the vector store")
    parser.add_argument("--source", default=None, help="Filter by source_id (e.g. 'harmbench')")
    parser.add_argument("--id", default=None, help="Show a specific chunk by ID (e.g. 'harmbench_c01')")
    parser.add_argument("--limit", type=int, default=10, help="Number of chunks to show (default 10)")
    parser.add_argument("--stats", action="store_true", help="Show per-source statistics only")
    args = parser.parse_args()

    client = chromadb.PersistentClient(path=str(VECTOR_STORE_DIR))
    collection = client.get_collection(name=COLLECTION_NAME)

    if args.id:
        result = collection.get(ids=[args.id], include=["documents", "metadatas"])
        if result["ids"]:
            meta = result["metadatas"][0]
            text = result["documents"][0]
            print(f"Chunk ID: {args.id}")
            print(f"Source:   {meta.get('source_id')}")
            print(f"Paper:    {meta.get('title')}")
            print(f"Section:  {meta.get('section_title')}")
            print(f"Year:     {meta.get('year')}")
            print(f"Length:   {len(text)} chars")
            print(f"\n--- Text ---\n{text}")
        else:
            print(f"Chunk '{args.id}' not found.")
        return

    # Get all chunks
    all_data = collection.get(include=["metadatas", "documents"])

    if args.stats:
        sources = {}
        for meta, doc in zip(all_data["metadatas"], all_data["documents"]):
            sid = meta.get("source_id", "unknown")
            if sid not in sources:
                sources[sid] = {"count": 0, "total_chars": 0, "title": meta.get("title", "")}
            sources[sid]["count"] += 1
            sources[sid]["total_chars"] += len(doc)

        print(f"{'source_id':35s} {'chunks':>6s} {'avg_chars':>9s}  title")
        print("-" * 100)
        for sid in sorted(sources):
            s = sources[sid]
            avg = s["total_chars"] // s["count"]
            print(f"{sid:35s} {s['count']:6d} {avg:9d}  {s['title'][:50]}")
        print(f"\nTotal: {len(all_data['ids'])} chunks")
        return

    # Filter and display
    indices = range(len(all_data["ids"]))
    if args.source:
        indices = [i for i in indices if all_data["metadatas"][i].get("source_id") == args.source]

    for i in list(indices)[:args.limit]:
        cid = all_data["ids"][i]
        meta = all_data["metadatas"][i]
        text = all_data["documents"][i]
        print(f"\n{'='*60}")
        print(f"[{cid}] section: {meta.get('section_title', '?')}")
        print(f"  paper: {meta.get('title', '?')[:80]}")
        print(f"  chars: {len(text)}")
        print(f"--- {text[:500]}{'...' if len(text) > 500 else ''}")


if __name__ == "__main__":
    main()
