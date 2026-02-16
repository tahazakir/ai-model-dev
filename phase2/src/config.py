"""Shared configuration for the RAG pipeline."""

from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────
PHASE2_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = PHASE2_DIR / "data"
RAW_PDF_DIR = DATA_DIR / "raw"
VECTOR_STORE_DIR = DATA_DIR / "vector_store"
LOGS_DIR = PHASE2_DIR / "logs"
EVAL_DIR = PHASE2_DIR / "eval"
MANIFEST_PATH = PHASE2_DIR / "data_manifest.json"

# ── Embedding ──────────────────────────────────────────────────────────
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"

# ── LLM (Ollama) ──────────────────────────────────────────────────────
OLLAMA_MODEL = "qwen3:8b"

# ── Chunking ──────────────────────────────────────────────────────────
CHUNK_TARGET_TOKENS = 512
CHUNK_OVERLAP_TOKENS = 50
APPROX_CHARS_PER_TOKEN = 4  # rough heuristic for English text

CHUNK_TARGET_CHARS = CHUNK_TARGET_TOKENS * APPROX_CHARS_PER_TOKEN  # ~2048
CHUNK_OVERLAP_CHARS = CHUNK_OVERLAP_TOKENS * APPROX_CHARS_PER_TOKEN  # ~200

# ── ChromaDB ──────────────────────────────────────────────────────────
COLLECTION_NAME = "jailbreak_safety_papers"

# ── Retrieval ─────────────────────────────────────────────────────────
TOP_K = 5

# ── Logging ───────────────────────────────────────────────────────────
RUN_LOG_PATH = LOGS_DIR / "run_logs.jsonl"
PROMPT_TEMPLATE_VERSION = "v1"
