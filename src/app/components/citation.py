"""Citation rendering helpers for Streamlit display."""

import re


def render_citations_markdown(answer: str) -> str:
    """
    Replace [source_id, chunk_id] citations with bold styled text in markdown.
    """
    pattern = r"\[([a-z0-9_.\- ]+),\s*([a-z0-9_]+_c\d+)\]"

    def replace_cite(match):
        source_id = match.group(1).strip()
        chunk_id = match.group(2).strip()
        return f"**[{source_id}, {chunk_id}]**"

    return re.sub(pattern, replace_cite, answer, flags=re.IGNORECASE)


def extract_unique_sources(answer: str) -> list[str]:
    """Extract unique source_ids from citations in an answer."""
    pattern = r"\[([a-z0-9_.\- ]+),\s*([a-z0-9_]+_c\d+)\]"
    matches = re.findall(pattern, answer, re.IGNORECASE)
    return list({m[0].strip() for m in matches})
