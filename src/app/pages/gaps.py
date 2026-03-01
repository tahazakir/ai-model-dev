"""Gap Finder page: identify evidence gaps and suggest next retrieval steps."""

import json
from datetime import datetime

import streamlit as st

from config import MANIFEST_PATH, OUTPUTS_DIR, TOP_K
from ingest.embed import get_collection, load_embedder
from rag.generate import generate_answer, generate_gap_analysis
from rag.retrieve import retrieve_diversified
from app.components.citation import render_citations_markdown
from app.components.export import export_markdown, save_artifact

st.title("Gap Finder")
st.markdown(
    "Identify what evidence is missing in the corpus for a given research topic, "
    "and get suggestions for targeted next retrieval steps."
)


# ── Initialize resources ─────────────────────────────────────────────
@st.cache_resource
def init_resources():
    _client, collection = get_collection()
    embedder = load_embedder()
    return collection, embedder


try:
    collection, embedder = init_resources()
except Exception as e:
    st.error(f"Failed to load resources: {e}. Have you run `make ingest` first?")
    st.stop()


# ── Settings ────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Gap Finder Settings")
    num_chunks = st.slider("Evidence chunks to analyze", min_value=5, max_value=20, value=10)


# ── Topic input ─────────────────────────────────────────────────────
topic = st.text_area(
    "Research topic or question to analyze for gaps:",
    placeholder="e.g., Defenses against multi-turn jailbreak attacks",
    height=100,
)

if st.button("Find Gaps", type="primary", disabled=not topic.strip()):
    with st.spinner("Retrieving evidence and analyzing gaps..."):
        # Step 1: Retrieve relevant chunks
        chunks = retrieve_diversified(
            collection, embedder, topic.strip(),
            top_k=num_chunks,
        )

        # Step 2: Generate initial answer
        answer = generate_answer(topic.strip(), chunks)

        # Step 3: Analyze gaps
        gap_analysis = generate_gap_analysis(topic.strip(), answer, chunks)

    st.session_state["gap_result"] = {
        "topic": topic.strip(),
        "answer": answer,
        "gap_analysis": gap_analysis,
        "chunks": chunks,
        "timestamp": datetime.now().isoformat(),
    }


# ── Display results ─────────────────────────────────────────────────
if "gap_result" in st.session_state:
    result = st.session_state["gap_result"]

    st.divider()

    # Show current answer
    st.subheader("Current Evidence-Based Answer")
    styled_answer = render_citations_markdown(result["answer"])
    st.markdown(styled_answer)

    with st.expander(f"Retrieved {len(result['chunks'])} evidence chunks"):
        sources = {c["source_id"] for c in result["chunks"]}
        st.markdown(f"**Sources covered:** {', '.join(sorted(sources))}")
        for chunk in result["chunks"]:
            st.caption(
                f"[{chunk['source_id']}, {chunk['chunk_id']}] — "
                f"{chunk['section_title']} (dist: {chunk['distance']:.4f})"
            )

    # Show gap analysis
    st.divider()
    st.subheader("Evidence Gap Analysis")
    styled_gaps = render_citations_markdown(result["gap_analysis"])
    st.markdown(styled_gaps)

    # Export
    st.divider()
    st.subheader("Export")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_topic = result["topic"][:40].replace(" ", "_").replace("/", "_")
    filename = f"gap_analysis_{safe_topic}_{timestamp}"

    full_content = (
        f"# Gap Analysis: {result['topic']}\n\n"
        f"## Current Answer\n\n{result['answer']}\n\n"
        f"---\n\n{result['gap_analysis']}"
    )
    md_content = export_markdown(full_content, f"Gap Analysis: {result['topic']}")

    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "Download Markdown",
            data=md_content,
            file_name=f"{filename}.md",
            mime="text/markdown",
            use_container_width=True,
        )
    with col2:
        if st.button("Save to outputs/", key="save_gap_md", use_container_width=True):
            path = save_artifact(md_content, f"{filename}.md")
            st.success(f"Saved to {path}")
