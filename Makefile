.PHONY: install corpus ingest demo search serve test lint evals dagster clean

install:
	pip install -e ".[dev,orchestration]"

corpus:  ## Write the sample handbook to data/docs
	rag-ingest generate-corpus

ingest:  ## Bring the index in line with data/docs
	rag-ingest ingest

demo: clean corpus  ## Full ingest, no-op re-run, simulated edits, incremental run, search
	rag-ingest ingest
	rag-ingest ingest
	rag-ingest simulate-changes
	rag-ingest ingest
	rag-ingest status --fail-if-stale > /dev/null
	rag-ingest search "what to do when the checkpoint store fills up" -k 3

serve:
	uvicorn rag_ingest.api:app --port 8000

test:
	pytest

lint:
	ruff check .

evals:  ## Retrieval quality and incremental efficiency on the gold set, with thresholds
	python evals/run_evals.py

dagster:
	dagster dev -m orchestration.definitions

clean:
	rm -rf state data/docs
