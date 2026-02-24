"""Ingestion pipeline orchestrator: parse PDFs -> chunk -> embed -> store."""

import json
import sys
import time
from pathlib import Path

import torch

# Add src/ to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import MANIFEST_PATH, RAW_PDF_DIR, EMBEDDING_MODEL
from ingest.parse import parse_pdf, save_processed
from ingest.chunk import chunk_paper
from ingest.embed import load_embedder, init_collection, embed_and_store


def load_manifest() -> dict[str, dict]:
    """Load data manifest and index by filename."""
    with open(MANIFEST_PATH) as f:
        entries = json.load(f)
    return {entry["filename"]: entry for entry in entries}


def ingest():
    """Run the full ingestion pipeline."""
    print("=" * 60)
    print("RAG Ingestion Pipeline")
    print("=" * 60)

    # Load manifest for metadata
    manifest = load_manifest()
    print(f"Loaded manifest with {len(manifest)} entries")

    # Initialize embedding model
    print(f"Loading embedding model: {EMBEDDING_MODEL} ...")
    embedder = load_embedder()
    print("  Embedding model loaded.")

    # Initialize ChromaDB (fresh collection)
    _client, collection = init_collection(reset=True)
    print(f"  Created fresh collection")

    # Process each PDF
    pdf_files = sorted(RAW_PDF_DIR.glob("*.pdf"))
    print(f"\nFound {len(pdf_files)} PDFs to process\n")

    total_chunks = 0
    paper_stats: list[dict] = []

    for pdf_path in pdf_files:
        filename = pdf_path.name
        source_id = pdf_path.stem.lower().replace(" ", "_")
        meta = manifest.get(filename, {})

        print(f"[{filename}]")

        # Parse PDF into sections
        t0 = time.time()
        try:
            sections = parse_pdf(pdf_path)
        except Exception as e:
            print(f"  ERROR parsing: {e}")
            continue
        parse_time = time.time() - t0
        print(f"  Parsed {len(sections)} sections in {parse_time:.1f}s")

        # Save processed text
        save_processed(source_id, filename, sections)

        # Chunk sections
        chunks = chunk_paper(sections, source_id)
        print(f"  Created {len(chunks)} chunks")

        if not chunks:
            print("  WARNING: No chunks created, skipping.")
            continue

        # Embed and store
        t0 = time.time()
        embed_and_store(embedder, collection, chunks, meta)
        embed_time = time.time() - t0
        print(f"  Embedded and stored in {embed_time:.1f}s")

        # Free MPS GPU memory between papers to prevent accumulation
        if torch.backends.mps.is_available():
            torch.mps.empty_cache()

        total_chunks += len(chunks)
        paper_stats.append({
            "filename": filename,
            "source_id": source_id,
            "sections": len(sections),
            "chunks": len(chunks),
        })
        print()

    # Summary
    print("=" * 60)
    print("Ingestion Summary")
    print("=" * 60)
    print(f"Papers processed: {len(paper_stats)}")
    print(f"Total chunks:     {total_chunks}")
    print(f"\nPer-paper breakdown:")
    for s in paper_stats:
        print(f"  {s['source_id']:30s}  sections={s['sections']:3d}  chunks={s['chunks']:3d}")
    print()


if __name__ == "__main__":
    ingest()
