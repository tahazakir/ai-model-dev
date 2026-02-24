"""Evaluation metrics for RAG pipeline: citation precision, groundedness, source recall."""

import re


def extract_citations(answer: str) -> list[tuple[str, str]]:
    """
    Extract [source_id, chunk_id] citations from an answer.
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
    flags_missing = (
        "evidence missing" in answer.lower()
        or "not contain" in answer.lower()
        or "no evidence" in answer.lower()
        or "insufficient evidence" in answer.lower()
    )

    if not expected_sources:
        return {
            "should_flag_missing": True,
            "correctly_flags_missing": flags_missing,
        }
    return {
        "should_flag_missing": False,
        "correctly_flags_missing": None,
    }
