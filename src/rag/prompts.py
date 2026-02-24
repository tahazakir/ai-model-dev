"""System prompts and templates for the RAG pipeline."""

SYSTEM_PROMPT = """\
You are a research assistant answering questions about LLM safety and jailbreaking research.

STRICT RULES:
1. ONLY use information from the provided context chunks. Do NOT use prior knowledge.
2. For EVERY claim you make, cite the source using EXACTLY this format: [source_id, chunk_id]
   Example: [harmbench, harmbench_c05]
   Do NOT add labels like "source_id:" or "chunk_id:" inside the brackets.
3. If the context does not contain sufficient evidence to answer fully, state what IS available
   with citations, then note what evidence is missing. Only use the full "EVIDENCE MISSING"
   response when the context contains NO relevant information at all.
4. If evidence conflicts across sources, explicitly flag the conflict with citations to both sides.
5. Do NOT invent or fabricate any citations. Only cite chunk IDs that appear in the context below.
6. When comparing multiple topics/papers, address each one explicitly using evidence from
   different sources. If evidence for one topic is missing, say so while still citing what you have.
7. Answer in a clear, concise manner with structured paragraphs."""

CONTEXT_TEMPLATE = """\
Context chunks (use these to answer):
{chunks}

Question: {query}"""

EVIDENCE_TABLE_PROMPT = """\
Given the following research evidence chunks, create a structured evidence table.
For each distinct claim or finding, extract:
- Claim: A concise statement of the finding
- Evidence: The key quote or paraphrase (max 2 sentences)
- Citation: [source_id, chunk_id] from the chunk
- Confidence: HIGH (directly stated), MEDIUM (implied/partial), LOW (tangential)
- Notes: Any caveats, conflicts, or limitations

Format as a markdown table with columns: Claim | Evidence | Citation | Confidence | Notes
Include 6-10 rows covering the most important findings.
Only use evidence from the provided chunks. If a claim has conflicting evidence, include
separate rows for each side with appropriate citations.

Context chunks:
{chunks}

Topic: {topic}"""

SYNTHESIS_MEMO_PROMPT = """\
Write a synthesis memo (800-1200 words) on the following topic based ONLY on the
provided research evidence. Structure it as:

1. **Introduction** (1-2 paragraphs): Frame the research question and its significance.
2. **Key Findings** (3-4 paragraphs): Synthesize evidence across sources. Every claim
   must have an inline citation in [source_id, chunk_id] format.
3. **Conflicts and Gaps**: Note where sources disagree or where evidence is missing.
4. **Conclusion** (1 paragraph): Summarize the state of knowledge.
5. **References**: List all cited sources with full metadata (title, authors, year, venue).

Evidence chunks:
{chunks}

Source metadata (for the reference list):
{metadata}

Topic: {topic}"""


def format_chunk_for_prompt(chunk_id: str, source_id: str, title: str, text: str) -> str:
    """Format a single chunk for inclusion in the prompt."""
    return f"[{source_id}, {chunk_id}] (from: {title})\n{text}"
