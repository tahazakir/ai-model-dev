"""Artifact Generator page: create evidence tables and synthesis memos."""

import json
from datetime import datetime

import streamlit as st

from config import MANIFEST_PATH, OUTPUTS_DIR, THREADS_DIR
from ingest.embed import get_collection, load_embedder
from rag.generate import generate_evidence_table, generate_synthesis_memo
from rag.retrieve import retrieve_diversified
from app.components.citation import render_citations_markdown
from app.components.export import (
    export_csv_from_markdown_table,
    export_markdown,
    export_pdf,
    save_artifact,
)

st.title("Artifact Generator")
st.markdown("Generate research artifacts from your corpus: evidence tables and synthesis memos.")


# ── Initialize resources ─────────────────────────────────────────────
@st.cache_resource
def init_resources():
    _client, collection = get_collection()
    embedder = load_embedder()
    return collection, embedder


@st.cache_data
def load_manifest_data():
    with open(MANIFEST_PATH) as f:
        return json.load(f)


try:
    collection, embedder = init_resources()
    manifest = load_manifest_data()
except Exception as e:
    st.error(f"Failed to load resources: {e}. Have you run `make ingest` first?")
    st.stop()


# ── Artifact type selection ──────────────────────────────────────────
artifact_type = st.selectbox(
    "Artifact Type:",
    ["Evidence Table", "Synthesis Memo"],
)

# ── Topic input ──────────────────────────────────────────────────────
st.subheader("Topic")

input_method = st.radio(
    "How would you like to provide the topic?",
    ["Enter a topic", "Select from a research thread"],
    horizontal=True,
)

topic = ""
if input_method == "Enter a topic":
    topic = st.text_area(
        "Research topic or question:",
        placeholder="e.g., Multi-turn jailbreak attack strategies and their effectiveness",
        height=80,
    )
else:
    # Load threads
    THREADS_DIR.mkdir(parents=True, exist_ok=True)
    thread_files = sorted(THREADS_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    threads = []
    for tf in thread_files:
        try:
            with open(tf) as f:
                threads.append(json.load(f))
        except Exception:
            pass

    if threads:
        thread_labels = [f"{t['title']} ({len(t.get('entries', []))} entries)" for t in threads]
        selected_idx = st.selectbox("Select thread:", range(len(threads)), format_func=lambda i: thread_labels[i])
        thread = threads[selected_idx]

        # Extract topic from thread entries
        queries = [e["query_text"] for e in thread.get("entries", [])]
        topic = st.text_area(
            "Topic (derived from thread queries):",
            value="; ".join(queries),
            height=80,
        )
    else:
        st.warning("No threads found. Use Search & Ask to create one, or enter a topic manually.")

# ── Retrieval settings ───────────────────────────────────────────────
with st.sidebar:
    st.header("Artifact Settings")
    num_chunks = st.slider(
        "Number of evidence chunks",
        min_value=5,
        max_value=20,
        value=12 if artifact_type == "Synthesis Memo" else 10,
    )
    max_per_source = st.slider(
        "Max chunks per source",
        min_value=1,
        max_value=5,
        value=3,
    )

# ── Generate artifact ────────────────────────────────────────────────
if st.button("Generate Artifact", type="primary", disabled=not topic.strip()):
    with st.spinner(f"Generating {artifact_type.lower()}... This may take a moment."):
        # Retrieve diverse chunks
        chunks = retrieve_diversified(
            collection, embedder, topic.strip(),
            top_k=num_chunks,
            max_per_source=max_per_source,
        )

        if not chunks:
            st.error("No relevant chunks found. Try a different topic.")
            st.stop()

        if artifact_type == "Evidence Table":
            content = generate_evidence_table(topic.strip(), chunks)
        else:
            # Get metadata for cited sources
            source_ids = {c["source_id"] for c in chunks}
            source_metadata = [m for m in manifest if any(
                sid in m.get("filename", "").lower().replace(" ", "_").replace(".pdf", "")
                for sid in source_ids
            )]
            content = generate_synthesis_memo(topic.strip(), chunks, source_metadata)

    # Store result
    st.session_state["artifact"] = {
        "type": artifact_type,
        "topic": topic.strip(),
        "content": content,
        "chunks": chunks,
        "timestamp": datetime.now().isoformat(),
    }


# ── Display artifact ─────────────────────────────────────────────────
if "artifact" in st.session_state:
    artifact = st.session_state["artifact"]

    st.divider()
    st.subheader(f"{artifact['type']}: {artifact['topic'][:80]}")

    # Render content
    styled_content = render_citations_markdown(artifact["content"])
    st.markdown(styled_content)

    # Show source chunks
    with st.expander(f"Source evidence ({len(artifact['chunks'])} chunks)"):
        for chunk in artifact["chunks"]:
            st.markdown(
                f"**[{chunk['source_id']}, {chunk['chunk_id']}]** — {chunk['section_title']}"
            )
            st.text(chunk["text"][:400])
            st.divider()

    # ── Export ────────────────────────────────────────────────────────
    st.divider()
    st.subheader("Export")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_topic = artifact["topic"][:40].replace(" ", "_").replace("/", "_")
    base_filename = f"{artifact['type'].lower().replace(' ', '_')}_{safe_topic}_{timestamp}"

    col1, col2, col3 = st.columns(3)

    with col1:
        md_content = export_markdown(artifact["content"], f"{artifact['type']}: {artifact['topic']}")
        st.download_button(
            "Download Markdown",
            data=md_content,
            file_name=f"{base_filename}.md",
            mime="text/markdown",
            use_container_width=True,
        )
        if st.button("Save Markdown to outputs/", key="save_md", use_container_width=True):
            path = save_artifact(md_content, f"{base_filename}.md")
            st.success(f"Saved to {path}")

    with col2:
        if artifact["type"] == "Evidence Table":
            csv_content = export_csv_from_markdown_table(artifact["content"])
            st.download_button(
                "Download CSV",
                data=csv_content,
                file_name=f"{base_filename}.csv",
                mime="text/csv",
                use_container_width=True,
            )
            if st.button("Save CSV to outputs/", key="save_csv", use_container_width=True):
                path = save_artifact(csv_content, f"{base_filename}.csv")
                st.success(f"Saved to {path}")
        else:
            st.button("CSV (tables only)", disabled=True, use_container_width=True)

    with col3:
        pdf_bytes = export_pdf(artifact["content"], f"{artifact['type']}: {artifact['topic']}")
        st.download_button(
            "Download PDF",
            data=pdf_bytes,
            file_name=f"{base_filename}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
        if st.button("Save PDF to outputs/", key="save_pdf", use_container_width=True):
            path = save_artifact(pdf_bytes, f"{base_filename}.pdf")
            st.success(f"Saved to {path}")
