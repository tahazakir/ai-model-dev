"""Disagreement Map page: surface agreements and conflicts across sources."""

from datetime import datetime

import streamlit as st

from config import OUTPUTS_DIR, TOP_K
from ingest.embed import get_collection, load_embedder
from rag.generate import generate_disagreement_map
from rag.retrieve import retrieve_diversified
from app.components.citation import render_citations_markdown
from app.components.export import (
    export_csv_from_markdown_table,
    export_markdown,
    save_artifact,
)

st.title("Disagreement Map")
st.markdown(
    "Identify where sources agree and disagree on a research topic. "
    "Conflicts are categorized by type and cited to specific passages."
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
    st.header("Disagreement Map Settings")
    num_chunks = st.slider("Evidence chunks to analyze", min_value=8, max_value=20, value=15)
    max_per_source = st.slider("Max chunks per source", min_value=2, max_value=5, value=3)
    st.caption("Use more chunks and higher per-source limits to find more disagreements.")


# ── Topic input ─────────────────────────────────────────────────────
topic = st.text_area(
    "Research topic to map disagreements:",
    placeholder="e.g., Effectiveness of automated red teaming approaches",
    height=100,
)

if st.button("Map Disagreements", type="primary", disabled=not topic.strip()):
    with st.spinner("Retrieving evidence and mapping disagreements..."):
        # Retrieve diverse chunks from multiple sources
        chunks = retrieve_diversified(
            collection, embedder, topic.strip(),
            top_k=num_chunks,
            max_per_source=max_per_source,
        )

        if not chunks:
            st.error("No relevant chunks found. Try a different topic.")
            st.stop()

        # Generate disagreement map
        disagreement_map = generate_disagreement_map(topic.strip(), chunks)

    st.session_state["disagreement_result"] = {
        "topic": topic.strip(),
        "disagreement_map": disagreement_map,
        "chunks": chunks,
        "timestamp": datetime.now().isoformat(),
    }


# ── Display results ─────────────────────────────────────────────────
if "disagreement_result" in st.session_state:
    result = st.session_state["disagreement_result"]

    st.divider()

    # Source coverage
    sources = {c["source_id"] for c in result["chunks"]}
    st.caption(f"Analyzed {len(result['chunks'])} chunks from {len(sources)} sources: {', '.join(sorted(sources))}")

    # Disagreement map
    st.subheader(f"Disagreement Map: {result['topic'][:80]}")
    styled_content = render_citations_markdown(result["disagreement_map"])
    st.markdown(styled_content)

    # Source evidence
    with st.expander(f"Source evidence ({len(result['chunks'])} chunks)"):
        for chunk in result["chunks"]:
            st.markdown(
                f"**[{chunk['source_id']}, {chunk['chunk_id']}]** — {chunk['section_title']}"
            )
            st.text(chunk["text"][:400])
            st.divider()

    # Export
    st.divider()
    st.subheader("Export")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_topic = result["topic"][:40].replace(" ", "_").replace("/", "_")
    base_filename = f"disagreement_map_{safe_topic}_{timestamp}"

    col1, col2, col3 = st.columns(3)

    with col1:
        md_content = export_markdown(
            result["disagreement_map"],
            f"Disagreement Map: {result['topic']}",
        )
        st.download_button(
            "Download Markdown",
            data=md_content,
            file_name=f"{base_filename}.md",
            mime="text/markdown",
            use_container_width=True,
        )
        if st.button("Save Markdown to outputs/", key="save_dis_md", use_container_width=True):
            path = save_artifact(md_content, f"{base_filename}.md")
            st.success(f"Saved to {path}")

    with col2:
        csv_content = export_csv_from_markdown_table(result["disagreement_map"])
        if csv_content.strip():
            st.download_button(
                "Download CSV (table)",
                data=csv_content,
                file_name=f"{base_filename}.csv",
                mime="text/csv",
                use_container_width=True,
            )
        else:
            st.button("CSV (no table found)", disabled=True, use_container_width=True)

    with col3:
        from app.components.export import export_pdf
        pdf_bytes = export_pdf(
            result["disagreement_map"],
            f"Disagreement Map: {result['topic']}",
        )
        st.download_button(
            "Download PDF",
            data=pdf_bytes,
            file_name=f"{base_filename}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
