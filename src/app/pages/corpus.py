"""Corpus Explorer page: browse papers, metadata, and chunk statistics."""

import json

import streamlit as st

from config import MANIFEST_PATH, PROCESSED_DIR, VECTOR_STORE_DIR
from ingest.embed import get_collection

st.title("Corpus Explorer")
st.markdown("Browse the research corpus: papers, metadata, and chunk statistics.")


# ── Load manifest ───────────────────────────────────────────────────
@st.cache_data
def load_manifest():
    with open(MANIFEST_PATH) as f:
        return json.load(f)


manifest = load_manifest()

# ── Corpus overview ─────────────────────────────────────────────────
st.subheader("Corpus Overview")
col1, col2, col3 = st.columns(3)
col1.metric("Total Papers", len(manifest))

years = [m["year"] for m in manifest if m.get("year")]
col2.metric("Year Range", f"{min(years)}–{max(years)}" if years else "N/A")

types = {m.get("source_type", m.get("type", "unknown")) for m in manifest}
col3.metric("Source Types", len(types))

# ── Filters ─────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Filters")

    all_years = sorted({m.get("year", 0) for m in manifest if m.get("year")})
    year_filter = st.multiselect("Year", all_years, default=all_years)

    all_types = sorted({m.get("source_type", m.get("type", "")) for m in manifest})
    type_filter = st.multiselect("Source Type", all_types, default=all_types)

    all_venues = sorted({m.get("venue", "") for m in manifest if m.get("venue")})
    venue_filter = st.multiselect("Venue", all_venues, default=all_venues)

    all_tags = sorted({t for m in manifest for t in m.get("tags", [])})
    tag_filter = st.multiselect("Tags", all_tags)

# ── Apply filters ───────────────────────────────────────────────────
filtered = manifest
if year_filter:
    filtered = [m for m in filtered if m.get("year") in year_filter]
if type_filter:
    filtered = [m for m in filtered if m.get("source_type", m.get("type")) in type_filter]
if venue_filter:
    filtered = [m for m in filtered if m.get("venue") in venue_filter or not m.get("venue")]
if tag_filter:
    filtered = [m for m in filtered if any(t in m.get("tags", []) for t in tag_filter)]

st.caption(f"Showing {len(filtered)} of {len(manifest)} papers")

# ── Paper list ──────────────────────────────────────────────────────
st.subheader("Papers")

for paper in sorted(filtered, key=lambda m: m.get("year", 0), reverse=True):
    source_id = paper.get("source_id", paper.get("filename", "").replace(".pdf", ""))
    title = paper.get("title", "Untitled")
    year = paper.get("year", "n.d.")
    authors = ", ".join(paper.get("authors", [])[:3])
    if len(paper.get("authors", [])) > 3:
        authors += " et al."
    venue = paper.get("venue", "")
    tags = paper.get("tags", [])

    with st.expander(f"**{title}** ({year}) — {source_id}"):
        st.markdown(f"**Authors:** {', '.join(paper.get('authors', []))}")
        st.markdown(f"**Year:** {year}")
        if venue:
            st.markdown(f"**Venue:** {venue}")
        st.markdown(f"**Type:** {paper.get('source_type', paper.get('type', 'unknown'))}")

        if paper.get("url_or_doi"):
            st.markdown(f"**DOI/URL:** {paper['url_or_doi']}")
        if paper.get("arxiv_url"):
            st.markdown(f"**arXiv:** {paper['arxiv_url']}")

        st.markdown(f"**Relevance:** {paper.get('relevance_note', 'N/A')}")

        if tags:
            st.markdown("**Tags:** " + " ".join(f"`{t}`" for t in tags))

        st.markdown(f"**Raw path:** `{paper.get('raw_path', 'N/A')}`")
        st.markdown(f"**Processed path:** `{paper.get('processed_path', 'N/A')}`")

        # Show processed sections if available
        processed_path = PROCESSED_DIR / f"{source_id}.json"
        if processed_path.exists():
            try:
                with open(processed_path) as f:
                    processed = json.load(f)
                sections = processed.get("sections", [])
                st.markdown(f"**Parsed sections:** {len(sections)}")
                for sec in sections[:10]:
                    sec_title = sec.get("title", "Untitled section")
                    sec_len = len(sec.get("text", ""))
                    st.caption(f"  - {sec_title} ({sec_len:,} chars)")
                if len(sections) > 10:
                    st.caption(f"  ... and {len(sections) - 10} more sections")
            except Exception:
                pass


# ── Tag cloud summary ───────────────────────────────────────────────
st.divider()
st.subheader("Tag Distribution")

tag_counts = {}
for m in manifest:
    for t in m.get("tags", []):
        tag_counts[t] = tag_counts.get(t, 0) + 1

if tag_counts:
    for tag, count in sorted(tag_counts.items(), key=lambda x: -x[1]):
        st.markdown(f"`{tag}` — {count} papers")
