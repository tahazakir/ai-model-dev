"""Evaluation Dashboard page: run eval suite and display metrics."""

import json
from pathlib import Path

import streamlit as st

from config import OUTPUTS_DIR

st.title("Evaluation Dashboard")
st.markdown("Run the evaluation query set and review metrics.")

EVAL_DIR = Path(__file__).resolve().parent.parent.parent / "eval"
EVAL_RESULTS_PATH = EVAL_DIR / "eval_results.json"


# ── Run evaluation ───────────────────────────────────────────────────
if st.button("Run Evaluation Suite", type="primary"):
    with st.spinner("Running 20 evaluation queries... This will take a few minutes."):
        try:
            from eval.runner import evaluate
            eval_data = evaluate()
            st.success(f"Evaluation complete! {eval_data['successful']}/{eval_data['total_queries']} queries succeeded.")
            st.rerun()
        except Exception as e:
            st.error(f"Evaluation failed: {e}")


# ── Load results ─────────────────────────────────────────────────────
if not EVAL_RESULTS_PATH.exists():
    st.info("No evaluation results found. Click 'Run Evaluation Suite' or run `make evaluate` from the terminal.")
    st.stop()

with open(EVAL_RESULTS_PATH) as f:
    eval_data = json.load(f)

st.caption(f"Last run: {eval_data.get('run_timestamp', 'unknown')} | Duration: {eval_data.get('total_time_s', 0):.1f}s")

# ── Aggregate metrics ────────────────────────────────────────────────
st.subheader("Aggregate Metrics")

metrics = eval_data.get("aggregate_metrics", {})
col1, col2, col3, col4 = st.columns(4)
col1.metric("Queries", f"{eval_data.get('successful', 0)}/{eval_data.get('total_queries', 0)}")
col2.metric(
    "Citation Precision",
    f"{metrics.get('avg_citation_precision', 0):.1%}" if metrics.get("avg_citation_precision") is not None else "N/A",
)
col3.metric(
    "Groundedness",
    f"{metrics.get('avg_groundedness', 0):.1%}" if metrics.get("avg_groundedness") is not None else "N/A",
)
col4.metric(
    "Source Recall",
    f"{metrics.get('avg_source_recall', 0):.1%}" if metrics.get("avg_source_recall") is not None else "N/A",
)


# ── Per-type breakdown ───────────────────────────────────────────────
st.subheader("Per-Type Breakdown")

results = eval_data.get("results", [])
successful = [r for r in results if "error" not in r]

type_stats = {}
for r in successful:
    qtype = r.get("query_type", "unknown")
    if qtype not in type_stats:
        type_stats[qtype] = {"count": 0, "citation_prec": [], "groundedness": [], "latency": []}
    type_stats[qtype]["count"] += 1
    type_stats[qtype]["citation_prec"].append(r.get("citation_validity", {}).get("citation_precision", 0))
    type_stats[qtype]["groundedness"].append(r.get("groundedness", {}).get("groundedness_score", 0))
    type_stats[qtype]["latency"].append(r.get("latency_ms", 0))

if type_stats:
    cols = st.columns(len(type_stats))
    for col, (qtype, stats) in zip(cols, type_stats.items()):
        with col:
            avg_cp = sum(stats["citation_prec"]) / len(stats["citation_prec"]) if stats["citation_prec"] else 0
            avg_g = sum(stats["groundedness"]) / len(stats["groundedness"]) if stats["groundedness"] else 0
            avg_lat = sum(stats["latency"]) / len(stats["latency"]) if stats["latency"] else 0

            st.markdown(f"**{qtype}** (n={stats['count']})")
            st.metric("Citation Precision", f"{avg_cp:.1%}")
            st.metric("Groundedness", f"{avg_g:.1%}")
            st.metric("Avg Latency", f"{avg_lat:.0f}ms")


# ── Per-query results ────────────────────────────────────────────────
st.subheader("Per-Query Results")

# Filter by type
type_filter = st.selectbox(
    "Filter by type:",
    ["All"] + list(type_stats.keys()),
)

filtered = successful if type_filter == "All" else [r for r in successful if r.get("query_type") == type_filter]

for r in filtered:
    citation_prec = r.get("citation_validity", {}).get("citation_precision", 0)
    groundedness = r.get("groundedness", {}).get("groundedness_score", 0)
    source_recall = r.get("source_recall")

    header = (
        f"**{r.get('query_id', '')}** ({r.get('query_type', '')}) — "
        f"CP: {citation_prec:.0%} | G: {groundedness:.0%}"
    )
    if source_recall is not None:
        header += f" | SR: {source_recall:.0%}"

    with st.expander(header):
        st.markdown(f"**Query:** {r.get('query_text', '')}")
        st.markdown(f"**Latency:** {r.get('latency_ms', 0):.0f}ms")

        st.markdown("**Retrieved Sources:** " + ", ".join(r.get("retrieved_sources", [])))
        if r.get("expected_sources"):
            st.markdown("**Expected Sources:** " + ", ".join(r["expected_sources"]))

        st.divider()
        st.markdown("**Answer:**")
        st.markdown(r.get("answer", ""))

        # Citation details
        cv = r.get("citation_validity", {})
        if cv.get("invalid_ids"):
            st.warning(f"Invalid citation IDs: {', '.join(cv['invalid_ids'])}")

        g = r.get("groundedness", {})
        if g.get("ungrounded_ids"):
            st.warning(f"Ungrounded citation IDs: {', '.join(g['ungrounded_ids'])}")

        eh = r.get("evidence_handling", {})
        if eh.get("should_flag_missing"):
            if eh.get("correctly_flags_missing"):
                st.success("Correctly flagged missing evidence")
            else:
                st.error("Failed to flag missing evidence")


# ── Export evaluation summary ────────────────────────────────────────
st.divider()
summary_md = f"""# Evaluation Summary

- **Run timestamp:** {eval_data.get('run_timestamp', 'unknown')}
- **Total queries:** {eval_data.get('total_queries', 0)}
- **Successful:** {eval_data.get('successful', 0)}
- **Duration:** {eval_data.get('total_time_s', 0):.1f}s

## Aggregate Metrics
- Citation Precision: {metrics.get('avg_citation_precision', 0):.2%}
- Groundedness: {metrics.get('avg_groundedness', 0):.2%}
- Source Recall: {metrics.get('avg_source_recall', 'N/A')}
"""

st.download_button(
    "Download Evaluation Summary (Markdown)",
    data=summary_md,
    file_name="evaluation_summary.md",
    mime="text/markdown",
)
