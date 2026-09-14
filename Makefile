.PHONY: install test lint format check demo clean

install:
	uv sync

test:
	uv run pytest -q

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests

format:
	uv run ruff format src tests
	uv run ruff check --fix src tests

check: lint test

demo:
	@for name in tool_server gateway stream_guard router; do bash scripts/demo_$$name.sh; done

clean:
	rm -rf var .pytest_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
