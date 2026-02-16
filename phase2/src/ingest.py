#!/usr/bin/env python3
"""
Ingestion pipeline: parse PDFs → section-aware chunking → embed → store in ChromaDB.
"""

import json
import re
import sys
import time
from pathlib import Path

import chromadb
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from sentence_transformers import SentenceTransformer

from config import (
    CHUNK_OVERLAP_CHARS,
    CHUNK_TARGET_CHARS,
    COLLECTION_NAME,
    EMBEDDING_MODEL,
    MANIFEST_PATH,
    RAW_PDF_DIR,
    VECTOR_STORE_DIR,
)

# ── Text cleaning ──────────────────────────────────────────────────────


def remove_latex(text: str) -> str:
    """Remove LaTeX content, keeping only plain text."""
    text = re.sub(r"\$\$.*?\$\$", "", text, flags=re.DOTALL)
    text = re.sub(r"\$[^\$]+\$", "", text)
    text = re.sub(r"\\begin\{[^}]+\}.*?\\end\{[^}]+\}", "", text, flags=re.DOTALL)
    text = re.sub(r"\\[a-zA-Z]+\{[^}]*\}", "", text)
    text = re.sub(r"\\[a-zA-Z]+", "", text)
    text = re.sub(r"\\[^a-zA-Z\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def clean_text(text: str) -> str:
    """Clean extracted text: remove LaTeX, images, footnotes."""
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)  # markdown images
    text = re.sub(r"^\[\^?\d+\].*$", "", text, flags=re.MULTILINE)  # footnotes
    text = remove_latex(text)
    text = re.sub(r"\n{3,}", "\n\n", text)  # collapse blank lines
    return text.strip()


# ── PDF parsing with docling ──────────────────────────────────────────


def parse_pdf(pdf_path: Path) -> list[tuple[str, str]]:
    """
    Parse a PDF with docling and return a list of (section_title, text) tuples.
    Uses the document structure for section-aware extraction.
    """
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = False
    pipeline_options.do_table_structure = True
    pipeline_options.generate_page_images = False
    pipeline_options.generate_picture_images = False

    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
        }
    )

    result = converter.convert(str(pdf_path))

    # Try structured extraction first
    sections = _extract_sections_structured(result)

    # Fall back to markdown header parsing
    if not sections:
        md = result.document.export_to_markdown()
        sections = _extract_sections_markdown(md)

    # Last resort: full document as one section
    if not sections:
        md = result.document.export_to_markdown()
        cleaned = clean_text(md)
        if cleaned:
            sections = [("Full Document", cleaned)]

    return sections


def _extract_sections_structured(result) -> list[tuple[str, str]]:
    """Extract sections from docling's document structure."""
    skip_types = {
        "Picture", "Figure", "Image", "Footnote", "Reference", "Caption",
        "Formula", "Equation",
    }

    sections: list[tuple[str, str]] = []
    current_title = None
    current_parts: list[str] = []

    for element, _level in result.document.iterate_items():
        etype = element.__class__.__name__

        if etype in skip_types:
            continue
        if hasattr(element, "label") and element.label:
            label_lower = element.label.lower()
            if any(s in label_lower for s in ["figure", "image", "picture",
                                               "footnote", "caption",
                                               "formula", "equation", "math"]):
                continue

        is_header = etype in ("SectionHeader", "Title", "Heading") or (
            hasattr(element, "label")
            and element.label
            and "heading" in element.label.lower()
        )

        if is_header and hasattr(element, "text"):
            if current_title and current_parts:
                content = clean_text("\n\n".join(current_parts))
                if content:
                    sections.append((current_title, content))
            current_title = element.text.strip()
            current_parts = []
        elif hasattr(element, "text") and element.text:
            text = element.text.strip()
            if text and not (text.startswith("$") or text.startswith("\\")):
                current_parts.append(text)

    # Flush last section
    if current_title and current_parts:
        content = clean_text("\n\n".join(current_parts))
        if content:
            sections.append((current_title, content))

    return sections


def _extract_sections_markdown(md_content: str) -> list[tuple[str, str]]:
    """Fall back: parse markdown headers to extract sections."""
    sections: list[tuple[str, str]] = []
    current_title = None
    current_lines: list[str] = []

    for line in md_content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("!["):
            continue
        if re.match(r"^\[\^?\d+\]", stripped):
            continue
        if stripped.startswith("$") or stripped.startswith("\\begin"):
            continue

        header_match = re.match(r"^(#{1,3})\s+(.+)$", line)
        if header_match:
            if current_title and current_lines:
                content = clean_text("\n".join(current_lines))
                if content:
                    sections.append((current_title, content))
            current_title = header_match.group(2).strip()
            current_lines = []
        elif current_title:
            current_lines.append(line)

    if current_title and current_lines:
        content = clean_text("\n".join(current_lines))
        if content:
            sections.append((current_title, content))

    return sections


# ── Chunking ──────────────────────────────────────────────────────────


def split_section_into_chunks(
    text: str,
    max_chars: int = CHUNK_TARGET_CHARS,
    overlap_chars: int = CHUNK_OVERLAP_CHARS,
) -> list[str]:
    """
    Split a section that exceeds max_chars using sentence boundaries.
    Returns a list of chunk texts.
    """
    if len(text) <= max_chars:
        return [text]

    # Split on sentence boundaries
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for sentence in sentences:
        slen = len(sentence)
        if current_len + slen > max_chars and current:
            chunks.append(" ".join(current))
            # Overlap: keep last sentences up to overlap_chars
            overlap_parts: list[str] = []
            overlap_len = 0
            for s in reversed(current):
                if overlap_len + len(s) > overlap_chars:
                    break
                overlap_parts.insert(0, s)
                overlap_len += len(s)
            current = overlap_parts
            current_len = overlap_len

        current.append(sentence)
        current_len += slen

    if current:
        chunks.append(" ".join(current))

    return chunks


def chunk_paper(
    sections: list[tuple[str, str]], source_id: str
) -> list[dict]:
    """
    Convert parsed sections into sized chunks with metadata.
    Returns a list of chunk dicts with keys: chunk_id, source_id, section_title, text.
    """
    chunks: list[dict] = []
    chunk_counter = 1

    for section_title, section_text in sections:
        sub_chunks = split_section_into_chunks(section_text)
        for text in sub_chunks:
            chunk_id = f"{source_id}_c{chunk_counter:02d}"
            chunks.append({
                "chunk_id": chunk_id,
                "source_id": source_id,
                "section_title": section_title,
                "text": text,
            })
            chunk_counter += 1

    return chunks


# ── Main ingestion ────────────────────────────────────────────────────


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
    embedder = SentenceTransformer(EMBEDDING_MODEL)
    print("  Embedding model loaded.")

    # Initialize ChromaDB
    VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(VECTOR_STORE_DIR))

    # Delete existing collection if it exists (fresh ingest)
    try:
        client.delete_collection(COLLECTION_NAME)
        print(f"  Deleted existing collection '{COLLECTION_NAME}'")
    except Exception:
        pass

    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    print(f"  Created collection '{COLLECTION_NAME}'")

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

        # Chunk sections
        chunks = chunk_paper(sections, source_id)
        print(f"  Created {len(chunks)} chunks")

        if not chunks:
            print("  WARNING: No chunks created, skipping.")
            continue

        # Prepare data for ChromaDB
        ids = [c["chunk_id"] for c in chunks]
        documents = [c["text"] for c in chunks]
        metadatas = []
        for c in chunks:
            m = {
                "source_id": c["source_id"],
                "section_title": c["section_title"],
                "filename": filename,
                "title": meta.get("title", ""),
                "year": meta.get("year", 0),
                "type": meta.get("type", ""),
                "authors": ", ".join(meta.get("authors", [])),
            }
            metadatas.append(m)

        # Embed
        t0 = time.time()
        embeddings = embedder.encode(documents, show_progress_bar=False).tolist()
        embed_time = time.time() - t0
        print(f"  Embedded in {embed_time:.1f}s")

        # Store in ChromaDB
        collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

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
    print(f"Vector store:     {VECTOR_STORE_DIR}")
    print(f"\nPer-paper breakdown:")
    for s in paper_stats:
        print(f"  {s['source_id']:30s}  sections={s['sections']:3d}  chunks={s['chunks']:3d}")
    print()


if __name__ == "__main__":
    ingest()
