"""LLM generation using Claude API (with Ollama fallback)."""

import os

from anthropic import Anthropic

from config import LLM_MODEL, LLM_MODEL_ARTIFACTS
from rag.prompts import (
    CONTEXT_TEMPLATE,
    EVIDENCE_TABLE_PROMPT,
    SYNTHESIS_MEMO_PROMPT,
    SYSTEM_PROMPT,
    format_chunk_for_prompt,
)


def _get_client() -> Anthropic:
    """Get Anthropic client."""
    return Anthropic()


def generate_answer(query: str, chunks: list[dict], model: str | None = None) -> str:
    """Generate an answer using Claude API with retrieved context."""
    if not chunks:
        return (
            "EVIDENCE MISSING: The corpus does not contain sufficient evidence "
            "to answer this question. Consider refining your query or adding "
            "more sources to the corpus."
        )

    model = model or LLM_MODEL

    # Format chunks for prompt
    chunk_texts = [
        format_chunk_for_prompt(c["chunk_id"], c["source_id"], c["title"], c["text"])
        for c in chunks
    ]
    chunks_str = "\n\n---\n\n".join(chunk_texts)
    user_message = CONTEXT_TEMPLATE.format(chunks=chunks_str, query=query)

    client = _get_client()
    message = client.messages.create(
        model=model,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    return message.content[0].text


def generate_evidence_table(
    topic: str, chunks: list[dict], model: str | None = None
) -> str:
    """Generate an evidence table artifact using Claude."""
    model = model or LLM_MODEL_ARTIFACTS

    chunk_texts = [
        format_chunk_for_prompt(c["chunk_id"], c["source_id"], c["title"], c["text"])
        for c in chunks
    ]
    chunks_str = "\n\n---\n\n".join(chunk_texts)
    user_message = EVIDENCE_TABLE_PROMPT.format(chunks=chunks_str, topic=topic)

    client = _get_client()
    message = client.messages.create(
        model=model,
        max_tokens=4096,
        system="You are a research analyst creating structured evidence tables from academic sources. Be precise with citations.",
        messages=[{"role": "user", "content": user_message}],
    )

    return message.content[0].text


def generate_synthesis_memo(
    topic: str, chunks: list[dict], source_metadata: list[dict], model: str | None = None
) -> str:
    """Generate a synthesis memo artifact using Claude."""
    model = model or LLM_MODEL_ARTIFACTS

    chunk_texts = [
        format_chunk_for_prompt(c["chunk_id"], c["source_id"], c["title"], c["text"])
        for c in chunks
    ]
    chunks_str = "\n\n---\n\n".join(chunk_texts)

    # Format metadata for reference list
    metadata_str = "\n".join(
        f"- {m.get('source_id', 'unknown')}: {m.get('title', 'Untitled')} "
        f"by {', '.join(m.get('authors', []))} ({m.get('year', 'n.d.')}). "
        f"{m.get('venue', '')}"
        for m in source_metadata
    )

    user_message = SYNTHESIS_MEMO_PROMPT.format(
        chunks=chunks_str, metadata=metadata_str, topic=topic
    )

    client = _get_client()
    message = client.messages.create(
        model=model,
        max_tokens=4096,
        system="You are a research synthesizer writing academic synthesis memos. Every claim must be cited. Be thorough but concise.",
        messages=[{"role": "user", "content": user_message}],
    )

    return message.content[0].text
