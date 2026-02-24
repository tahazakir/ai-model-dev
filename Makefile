.PHONY: setup ingest query query-filtered evaluate app run-all clean

# One-command setup
setup:
	uv sync

# Ingest all PDFs into ChromaDB
ingest:
	cd src && uv run python -m ingest.pipeline

# Single query (usage: make query TEXT="your question here")
query:
	cd src && uv run python -m rag.pipeline --text "$(TEXT)"

# Query with metadata filter (usage: make query-filtered TEXT="..." YEAR=2024)
query-filtered:
	cd src && uv run python -m rag.pipeline --text "$(TEXT)" $(if $(YEAR),--year $(YEAR)) $(if $(AUTHOR),--author "$(AUTHOR)") $(if $(TYPE),--type "$(TYPE)")

# Run full evaluation suite (20 queries)
evaluate:
	cd src && uv run python -m eval.runner

# Launch Streamlit app
app:
	uv run streamlit run src/app/main.py

# Full pipeline: setup → ingest → evaluate
run-all: setup ingest evaluate

# Remove vector store, logs, and outputs (keeps raw data)
clean:
	rm -rf data/vector_store data/processed logs/*.jsonl src/eval/eval_results.json outputs/*.md outputs/*.csv outputs/*.pdf
