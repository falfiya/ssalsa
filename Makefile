.PHONY: example
example:
	cd example; uv sync --reinstall
	uv run example/main.py
