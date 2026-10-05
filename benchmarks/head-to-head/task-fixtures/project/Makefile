.PHONY: build unit test setup
build:
	uv run python runner.py build
unit:
	uv run python runner.py unit
test: setup
	uv run python runner.py test
setup:
	uv run python runner.py setup
