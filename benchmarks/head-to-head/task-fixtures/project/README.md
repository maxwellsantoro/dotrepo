# Controlled measurement project

These source inputs exercise measurement plumbing; they are not an upstream
holdout or evidence of consumer benefit.

Build: `make build`. Unit tests: `make unit`.
Prerequisite test: `make test`; its Make prerequisite creates `ready`.
Parameterized test: `just test unit`; `target` is required.
Compilation mode `uv run python runner.py compile` exits zero without running tests.
For the component task, see `components/widget/README.md`.
