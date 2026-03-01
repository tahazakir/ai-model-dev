"""LLM generation using Claude API with response caching for reproducibility."""

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from anthropic import Anthropic

from config import CACHE_DIR, LLM_MODEL, LLM_MODEL_ARTIFACTS, REPLAY_MODE
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


def _cache_key(model: str, system: str, user_message: str) -> str:
    """Generate a deterministic cache key from the request parameters."""
    content = f"{model}||{system}||{user_message}"
    return hashlib.sha256(content.encode()).hexdigest()


def _cached_generate(model: str, system: str, user_message: str, max_tokens: int) -> str:
    """
    Generate a response with caching for reproducibility.

    - If a cached response exists, return it (regardless of REPLAY_MODE).
    - If REPLAY_MODE=true and no cache exists, raise an error.
    - Otherwise, call the Claude API, cache the response, and return it.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = _cache_key(model, system, user_message)
    cache_path = CACHE_DIR / f"{key}.json"

    # Check cache first
    if cache_path.exists():
        with open(cache_path) as f:
            cached = json.load(f)
        return cached["response"]

    # In replay mode, we must have a cache hit
    if REPLAY_MODE:
        raise RuntimeError(
            f"Cache miss in replay mode (key={key[:12]}...). "
            "Run the pipeline with REPLAY_MODE=false first to populate the cache."
        )

    # Call the API
    client = _get_client()
    message = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user_message}],
    )
    response_text = message.content[0].text

    # Save to cache
    cache_entry = {
        "model": model,
        "system_prompt_hash": hashlib.sha256(system.encode()).hexdigest()[:16],
        "user_message_hash": hashlib.sha256(user_message.encode()).hexdigest()[:16],
        "max_tokens": max_tokens,
        "response": response_text,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    with open(cache_path, "w") as f:
        json.dump(cache_entry, f, indent=2)

    return response_text


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

    return _cached_generate(model, SYSTEM_PROMPT, user_message, max_tokens=2048)


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

    system = "You are a research analyst creating structured evidence tables from academic sources. Be precise with citations."
    return _cached_generate(model, system, user_message, max_tokens=4096)


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

    system = "You are a research synthesizer writing academic synthesis memos. Every claim must be cited. Be thorough but concise."
    return _cached_generate(model, system, user_message, max_tokens=4096)


def generate_gap_analysis(
    topic: str, answer: str, chunks: list[dict], model: str | None = None
) -> str:
    """Analyze evidence gaps in the retrieved corpus for a given topic."""
    model = model or LLM_MODEL_ARTIFACTS

    chunk_texts = [
        format_chunk_for_prompt(c["chunk_id"], c["source_id"], c["title"], c["text"])
        for c in chunks
    ]
    chunks_str = "\n\n---\n\n".join(chunk_texts)

    from rag.prompts import GAP_ANALYSIS_PROMPT
    user_message = GAP_ANALYSIS_PROMPT.format(
        chunks=chunks_str, answer=answer, topic=topic
    )

    system = (
        "You are a research gap analyst. Identify what evidence is missing, "
        "what questions remain unanswered, and suggest targeted next retrieval steps."
    )
    return _cached_generate(model, system, user_message, max_tokens=4096)


def generate_disagreement_map(
    topic: str, chunks: list[dict], model: str | None = None
) -> str:
    """Identify agreements and disagreements across sources on a topic."""
    model = model or LLM_MODEL_ARTIFACTS

    chunk_texts = [
        format_chunk_for_prompt(c["chunk_id"], c["source_id"], c["title"], c["text"])
        for c in chunks
    ]
    chunks_str = "\n\n---\n\n".join(chunk_texts)

    from rag.prompts import DISAGREEMENT_MAP_PROMPT
    user_message = DISAGREEMENT_MAP_PROMPT.format(chunks=chunks_str, topic=topic)

    system = (
        "You are a research analyst identifying points of agreement and disagreement "
        "across academic sources. Be precise with citations and categorize conflicts."
    )
    return _cached_generate(model, system, user_message, max_tokens=4096)
