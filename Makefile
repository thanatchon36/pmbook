.PHONY: install lint test check reproduce analysis

install:
	uv sync

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy

test:
	uv run pytest

check: lint test

# Filled in Phases 2-4: raw -> panel -> figures -> paper.
reproduce:
	@echo "make reproduce: not implemented yet (Phases 2-4)" >&2; exit 2

analysis:
	@echo "make analysis: not implemented yet (Phase 3)" >&2; exit 2
