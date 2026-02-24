"""Research Threads page: view and manage saved research sessions."""

import json
from pathlib import Path

import streamlit as st

from config import THREADS_DIR
from app.components.citation import render_citations_markdown

st.title("Research Threads")
st.markdown("View and manage your saved research sessions.")


# ── Load threads ─────────────────────────────────────────────────────
THREADS_DIR.mkdir(parents=True, exist_ok=True)
thread_files = sorted(THREADS_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)

if not thread_files:
    st.info("No research threads saved yet. Use the Search & Ask page to create one.")
    st.stop()


# ── Thread list ──────────────────────────────────────────────────────
threads = []
for tf in thread_files:
    try:
        with open(tf) as f:
            td = json.load(f)
        td["_filepath"] = str(tf)
        threads.append(td)
    except Exception:
        pass

if not threads:
    st.info("No valid threads found.")
    st.stop()

# Thread selector
thread_labels = [
    f"{t['title']} ({len(t.get('entries', []))} entries, {t.get('updated_at', 'unknown')[:10]})"
    for t in threads
]
selected_idx = st.selectbox(
    "Select a thread:",
    range(len(threads)),
    format_func=lambda i: thread_labels[i],
)

thread = threads[selected_idx]


# ── Thread management ────────────────────────────────────────────────
col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    new_title = st.text_input("Rename thread:", value=thread["title"], key="rename_input")

with col2:
    if st.button("Rename", use_container_width=True):
        thread["title"] = new_title
        filepath = Path(thread["_filepath"])
        save_data = {k: v for k, v in thread.items() if k != "_filepath"}
        with open(filepath, "w") as f:
            json.dump(save_data, f, indent=2)
        st.success("Thread renamed!")
        st.rerun()

with col3:
    if st.button("Delete Thread", type="secondary", use_container_width=True):
        filepath = Path(thread["_filepath"])
        filepath.unlink()
        st.success("Thread deleted.")
        st.rerun()


# ── Thread entries ───────────────────────────────────────────────────
st.divider()
st.subheader(f"Thread: {thread['title']}")
st.caption(f"Created: {thread.get('created_at', 'unknown')[:19]} | Updated: {thread.get('updated_at', 'unknown')[:19]}")

entries = thread.get("entries", [])
for i, entry in enumerate(entries):
    st.markdown(f"### Query {i + 1}")
    st.markdown(f"**Q:** {entry['query_text']}")

    if entry.get("metadata_filters"):
        filters_str = ", ".join(f"{k}={v}" for k, v in entry["metadata_filters"].items())
        st.caption(f"Filters: {filters_str}")

    # Answer
    styled = render_citations_markdown(entry["answer"])
    st.markdown(styled)

    # Chunks
    chunks = entry.get("retrieved_chunks", [])
    if chunks:
        with st.expander(f"Retrieved {len(chunks)} chunks"):
            for chunk in chunks:
                st.markdown(
                    f"**[{chunk.get('source_id', '')}, {chunk.get('chunk_id', '')}]** — "
                    f"{chunk.get('section_title', '')} (dist: {chunk.get('distance', 0):.4f})"
                )
                st.text(chunk.get("text", "")[:500])
                st.divider()

    st.caption(f"Latency: {entry.get('latency_ms', 0):.0f}ms | {entry.get('timestamp', '')[:19]}")
    st.divider()
