.PHONY: setup ingest query evaluate run-all clean

# One-command setup
setup:
	uv sync

# Ingest all PDFs into ChromaDB
ingest:
	cd phase2/src && uv run python ingest.py

# Single query (usage: make query TEXT="your question here")
query:
	cd phase2/src && uv run python query.py --text "$(TEXT)"

# Query with metadata filter (usage: make query-filtered TEXT="..." YEAR=2024)
query-filtered:
	cd phase2/src && uv run python query.py --text "$(TEXT)" $(if $(YEAR),--year $(YEAR)) $(if $(AUTHOR),--author "$(AUTHOR)") $(if $(TYPE),--type "$(TYPE)")

# Run full evaluation suite (20 queries)
evaluate:
	cd phase2/src && uv run python evaluate.py

# Full pipeline: setup → ingest → evaluate
run-all: setup ingest evaluate

# Remove vector store and logs (keeps raw data)
clean:
	rm -rf phase2/data/vector_store phase2/logs/*.jsonl phase2/eval/eval_results.json
