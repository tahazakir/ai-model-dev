"""Shared configuration for the RAG pipeline."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# ── Paths ──────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
RAW_PDF_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
VECTOR_STORE_DIR = DATA_DIR / "vector_store"
MANIFEST_PATH = DATA_DIR / "data_manifest.json"
LOGS_DIR = ROOT_DIR / "logs"
OUTPUTS_DIR = ROOT_DIR / "outputs"
THREADS_DIR = OUTPUTS_DIR / "threads"
EVAL_DIR = Path(__file__).resolve().parent / "eval"

# ── Embedding ──────────────────────────────────────────────────────────
EMBEDDING_MODEL = "google/embeddinggemma-300m"
EMBEDDING_DIM = 768  # embeddinggemma-300m native output dimension

# ── LLM ────────────────────────────────────────────────────────────────
LLM_MODEL = os.getenv("LLM_MODEL", "claude-haiku-4-5-20251001")
LLM_MODEL_ARTIFACTS = os.getenv("LLM_MODEL_ARTIFACTS", "claude-sonnet-4-6-20250514")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# ── Chunking ──────────────────────────────────────────────────────────
CHUNK_TARGET_TOKENS = 1024
CHUNK_OVERLAP_TOKENS = 100
APPROX_CHARS_PER_TOKEN = 4  # rough heuristic for English text

CHUNK_TARGET_CHARS = CHUNK_TARGET_TOKENS * APPROX_CHARS_PER_TOKEN  # ~4096
CHUNK_OVERLAP_CHARS = CHUNK_OVERLAP_TOKENS * APPROX_CHARS_PER_TOKEN  # ~400

# ── ChromaDB ──────────────────────────────────────────────────────────
COLLECTION_NAME = "jailbreak_safety_papers"

# ── Retrieval ─────────────────────────────────────────────────────────
TOP_K = 8
MAX_PER_SOURCE = 3  # for source-diversified retrieval

# ── Logging ───────────────────────────────────────────────────────────
RUN_LOG_PATH = LOGS_DIR / "run_logs.jsonl"
PROMPT_TEMPLATE_VERSION = "v2"
