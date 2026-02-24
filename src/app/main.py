"""Streamlit entry point for the LLM Safety Research Portal."""

import sys
from pathlib import Path

# Add src/ to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

st.set_page_config(
    page_title="LLM Safety Research Portal",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Navigation
search_page = st.Page("pages/search.py", title="Search & Ask")
threads_page = st.Page("pages/threads.py", title="Research Threads")
artifacts_page = st.Page("pages/artifacts.py", title="Artifact Generator")
evaluation_page = st.Page("pages/evaluation.py", title="Evaluation")

pg = st.navigation([search_page, threads_page, artifacts_page, evaluation_page])
pg.run()
