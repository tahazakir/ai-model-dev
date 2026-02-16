# LLM Jailbreaking Safety Research — RAG Pipeline

Production RAG pipeline for querying a corpus of 17 LLM jailbreaking and safety research papers.

## Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager
- [Ollama](https://ollama.com/) for local LLM inference

### Ollama Setup

```bash
brew install ollama
ollama serve          # run in a separate terminal
ollama pull qwen3:8b  # download the model (~5GB)
```

## Quick Start (One Command)

```bash
make run-all
```

This runs: dependency install → PDF ingestion → full evaluation (20 queries).

## Step-by-Step Usage

```bash
# 1. Install dependencies
make setup

# 2. Ingest PDFs into ChromaDB vector store
make ingest

# 3. Ask a single question
make query TEXT="What is HarmBench?"

# 4. Query with metadata filters
make query-filtered TEXT="Compare attack methods" YEAR=2024

# 5. Run full evaluation suite
make evaluate
```

## Project Structure

```
phase2/
├── data/
│   ├── raw/              # 17 source PDFs
│   └── vector_store/     # ChromaDB persistent storage
├── src/
│   ├── config.py         # Shared configuration
│   ├── ingest.py         # PDF parsing → chunking → embedding → storage
│   ├── query.py          # Retrieval → generation → citation → logging
│   └── evaluate.py       # Evaluation runner with metrics
├── eval/
│   ├── queries.json      # 20 evaluation queries (10 direct, 5 synthesis, 5 edge-case)
│   └── eval_results.json # Evaluation output
├── logs/
│   └── run_logs.jsonl    # Machine-readable query logs
├── data_manifest.json    # Paper metadata (title, authors, year, DOI, arXiv)
└── CLAUDE.md             # Project guidelines
```

## Components

### Ingestion (`make ingest`)
- Parses PDFs with docling (section-aware extraction)
- Chunks by section headers with size regulation (~512 tokens, 50 token overlap)
- Embeds with BAAI/bge-small-en-v1.5
- Stores in ChromaDB with metadata (year, authors, type, title)

### Query (`make query TEXT="..."`)
- Retrieves top-5 chunks via cosine similarity
- Optional metadata filtering (year, author, document type)
- Generates cited answers via Ollama qwen3:8b
- Logs every interaction to `phase2/logs/run_logs.jsonl`
- Trust behavior: refuses to invent citations; flags missing evidence

### Evaluation (`make evaluate`)
- Runs 20 queries across 3 categories
- Computes: citation precision, groundedness, source recall
- Detects correct handling of missing-evidence edge cases
- Saves results to `phase2/eval/eval_results.json`

## Reproducibility

- All dependencies pinned in `pyproject.toml` and resolved in `uv.lock`
- Single command path: `make run-all` (setup → ingest → evaluate)
- Deterministic ingestion: same PDFs → same chunks → same embeddings
- Every query logs the exact prompt template version and model ID to `phase2/logs/run_logs.jsonl`

## Enhancement: Metadata Filtering

Filter retrieval by paper metadata using ChromaDB `where` clauses:

```bash
# Only retrieve from 2024 papers
make query-filtered TEXT="What jailbreak methods were proposed?" YEAR=2024

# Only retrieve from a specific author
make query-filtered TEXT="What benchmarks exist?" AUTHOR="Dan Hendrycks"
```
