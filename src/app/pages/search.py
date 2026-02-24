"""Search & Ask page: query the RAG pipeline with metadata filters."""

import json
import time
import uuid
from datetime import datetime
from pathlib import Path

import streamlit as st

from config import MANIFEST_PATH, THREADS_DIR, TOP_K
from ingest.embed import get_collection, load_embedder
from rag.generate import generate_answer
from rag.retrieve import retrieve_diversified
from rag.pipeline import log_interaction
from app.components.citation import render_citations_markdown, extract_unique_sources

st.title("Search & Ask")
st.markdown("Query the LLM safety research corpus with cited answers.")


# ── Initialize resources (cached) ────────────────────────────────────
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


# ── Sidebar filters ──────────────────────────────────────────────────
with st.sidebar:
    st.header("Filters")

    years = sorted({m.get("year", 0) for m in manifest if m.get("year")})
    year_filter = st.selectbox("Year", [None] + years, format_func=lambda x: "All years" if x is None else str(x))

    types = sorted({m.get("type", "") for m in manifest if m.get("type")})
    type_filter = st.selectbox("Document Type", [None] + types, format_func=lambda x: "All types" if x is None else x)

    author_filter = st.text_input("Author (substring match)", value="")
    author_filter = author_filter.strip() or None

    top_k = st.slider("Number of chunks to retrieve", min_value=3, max_value=15, value=TOP_K)

    st.divider()
    st.caption("Retrieval uses source-diversified search (max 3 chunks per paper).")


# ── Query input ──────────────────────────────────────────────────────
query_text = st.text_area(
    "Enter your research question:",
    placeholder="e.g., What does ASR measure in HarmBench and what are its known limitations?",
    height=100,
)

col1, col2 = st.columns([1, 4])
with col1:
    ask_button = st.button("Ask", type="primary", use_container_width=True)
with col2:
    pass


# ── Run query ────────────────────────────────────────────────────────
if ask_button and query_text.strip():
    with st.spinner("Retrieving and generating answer..."):
        t0 = time.time()

        # Retrieve
        chunks = retrieve_diversified(
            collection, embedder, query_text.strip(),
            top_k=top_k,
            year=year_filter,
            author=author_filter,
            doc_type=type_filter,
        )

        # Generate
        answer = generate_answer(query_text.strip(), chunks)
        latency_ms = (time.time() - t0) * 1000

        # Log
        filters = {}
        if year_filter:
            filters["year"] = year_filter
        if author_filter:
            filters["author"] = author_filter
        if type_filter:
            filters["type"] = type_filter
        log_interaction(query_text.strip(), filters, chunks, answer, latency_ms)

    # Store in session state
    st.session_state["last_result"] = {
        "query_text": query_text.strip(),
        "answer": answer,
        "chunks": chunks,
        "latency_ms": latency_ms,
        "filters": filters,
        "timestamp": datetime.now().isoformat(),
    }

# ── Display results ──────────────────────────────────────────────────
if "last_result" in st.session_state:
    result = st.session_state["last_result"]

    st.divider()

    # Answer
    st.subheader("Answer")
    styled_answer = render_citations_markdown(result["answer"])
    st.markdown(styled_answer)

    # Metadata
    sources_cited = extract_unique_sources(result["answer"])
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Latency", f"{result['latency_ms']:.0f}ms")
    col_b.metric("Chunks Retrieved", len(result["chunks"]))
    col_c.metric("Sources Cited", len(sources_cited))

    # Retrieved chunks
    st.subheader("Retrieved Sources")
    for i, chunk in enumerate(result["chunks"]):
        with st.expander(
            f"[{chunk['source_id']}, {chunk['chunk_id']}] — {chunk['section_title']} "
            f"(dist: {chunk['distance']:.4f})"
        ):
            st.markdown(f"**Paper:** {chunk['title']}")
            st.markdown(f"**Section:** {chunk['section_title']}")
            st.text(chunk["text"][:1500] + ("..." if len(chunk["text"]) > 1500 else ""))

    # Save to thread
    st.divider()
    st.subheader("Save to Research Thread")

    # List existing threads
    THREADS_DIR.mkdir(parents=True, exist_ok=True)
    thread_files = sorted(THREADS_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    thread_options = ["Create new thread"]
    thread_map = {}
    for tf in thread_files:
        try:
            with open(tf) as f:
                td = json.load(f)
            label = f"{td.get('title', 'Untitled')} ({len(td.get('entries', []))} entries)"
            thread_options.append(label)
            thread_map[label] = tf
        except Exception:
            pass

    selected_thread = st.selectbox("Select thread:", thread_options)
    new_thread_title = None
    if selected_thread == "Create new thread":
        new_thread_title = st.text_input("Thread title:", value=result["query_text"][:60])

    if st.button("Save to Thread"):
        entry = {
            "query_text": result["query_text"],
            "answer": result["answer"],
            "retrieved_chunks": result["chunks"],
            "metadata_filters": result["filters"],
            "timestamp": result["timestamp"],
            "latency_ms": result["latency_ms"],
        }

        if selected_thread == "Create new thread":
            thread_data = {
                "thread_id": str(uuid.uuid4()),
                "title": new_thread_title or result["query_text"][:60],
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "entries": [entry],
            }
            filepath = THREADS_DIR / f"{thread_data['thread_id']}.json"
        else:
            filepath = thread_map[selected_thread]
            with open(filepath) as f:
                thread_data = json.load(f)
            thread_data["entries"].append(entry)
            thread_data["updated_at"] = datetime.now().isoformat()

        with open(filepath, "w") as f:
            json.dump(thread_data, f, indent=2)

        st.success(f"Saved to thread: {thread_data['title']}")
