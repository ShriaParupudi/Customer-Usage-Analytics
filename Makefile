# Customer Usage Analytics Pipeline
# `make` is the DAG for this project: each target depends on the one before it.
# NOTE: recipe lines must be indented with a TAB, not spaces.

PYTHON := python

.PHONY: help all data ingest dq marts analytics export peek test lint clean

help:
	@echo "make all        - run the full pipeline end to end"
	@echo "make data       - Phase 1: generate synthetic raw datasets"
	@echo "make ingest     - Phase 2: load raw files into DuckDB"
	@echo "make dq         - Phase 3: run data quality checks"
	@echo "make marts      - Phase 4: build staging + dimensional model"
	@echo "make analytics  - Phases 5-7: metrics, segments, risk scoring"
	@echo "make export     - Phase 8: export CSVs + build the HTML dashboard"
	@echo "make peek       - show row counts and a preview of every table"
	@echo "make test       - run pytest"
	@echo "make lint       - run ruff"
	@echo "make clean      - delete generated data and the warehouse"

all: data ingest dq marts analytics export
	@echo "Pipeline complete. See outputs/"

data:
	$(PYTHON) -m src.generate_data

ingest:
	$(PYTHON) -m src.ingest

dq:
	$(PYTHON) -m src.quality_checks

marts:
	$(PYTHON) -m src.build_staging
	$(PYTHON) -m src.build_marts

analytics:
	$(PYTHON) -m src.build_analytics

export:
	$(PYTHON) -m src.export_bi
	$(PYTHON) -m src.build_dashboard

peek:
	$(PYTHON) -m src.peek

test:
	pytest -q

lint:
	ruff check src tests

clean:
	rm -rf data/raw/*.csv data/raw/*.csv.gz data/raw/*.parquet data/raw/*.md data/interim/* data/warehouse/*.duckdb outputs/*.csv outputs/*.md
	@echo "Cleaned. Run 'make all' to rebuild from scratch."
