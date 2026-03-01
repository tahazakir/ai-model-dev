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


GAP_ANALYSIS_PROMPT = """\
You have been given a research topic, retrieved evidence chunks, and a generated answer.
Analyze the evidence and identify gaps. Produce a structured gap analysis:

## Evidence Coverage Summary
Briefly summarize what the corpus DOES cover on this topic (2-3 sentences).

## Identified Gaps
For each gap, provide:
- **Gap description**: What evidence is missing or insufficient
- **Importance**: HIGH / MEDIUM / LOW
- **Type**: methodological | empirical | theoretical | comparative
- **Current evidence**: What partial evidence exists (cite chunks if applicable)

## Suggested Next Retrieval Steps
For each gap, suggest:
- Specific search queries to find the missing evidence
- Types of sources that would fill the gap (e.g., "empirical study comparing X and Y")

Evidence chunks:
{chunks}

Current answer:
{answer}

Topic: {topic}"""

DISAGREEMENT_MAP_PROMPT = """\
Analyze the following research evidence chunks and identify points of agreement
and disagreement across different sources on the given topic.

Produce a structured disagreement map:

## Points of Agreement
List claims where multiple sources converge. For each:
- **Claim**: The shared finding
- **Supporting sources**: Citations [source_id, chunk_id] from each source
- **Strength**: STRONG (3+ sources) / MODERATE (2 sources) / WEAK (implied)

## Points of Disagreement
List claims where sources conflict or diverge. For each:
- **Topic**: The disputed area
- **Position A**: Source position with citation [source_id, chunk_id]
- **Position B**: Opposing/different position with citation [source_id, chunk_id]
- **Type**: methodological | empirical | definitional | scope
- **Notes**: Context for why the disagreement exists

## Unresolved Questions
Topics where the evidence is too sparse to determine agreement or disagreement.

Format disagreements as a markdown table:
| Topic | Position A | Position B | Type | Sources |
|-------|-----------|-----------|------|---------|

Evidence chunks:
{chunks}

Topic: {topic}"""


def format_chunk_for_prompt(chunk_id: str, source_id: str, title: str, text: str) -> str:
    """Format a single chunk for inclusion in the prompt."""
    return f"[{source_id}, {chunk_id}] (from: {title})\n{text}"
