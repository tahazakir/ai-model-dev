"""Chunking logic: split parsed sections into sized chunks with metadata."""

import re

from config import CHUNK_OVERLAP_CHARS, CHUNK_TARGET_CHARS


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
