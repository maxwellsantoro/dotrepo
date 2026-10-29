# Common image environment compatibility

The retained b47 image declares GOENV=off and GOTOOLCHAIN=local. The former runtime rejected both keys before container creation. This patch admits those exact inherited image defaults using a narrow image-only validator, while leaving caller ENV_KEYS unchanged. It injects no environment value. Unknown/unsafe values, duplicate keys, invalid names/types and control characters refuse before create. Null/empty Docker Env retains its prior meaning.

The before source/reproduction is retained. controls.py replays the exact immutable image-inspect metadata through an owned fake daemon, showing old rejection and new image/create/start/cleanup progression. No real daemon/provider/network/upstream action occurred. The synthetic qualifications solely exercise the mock boundary; they are not real authorization.

The focused runtime suite passes 167 tests including 42 new controls, and Ruff check/format passes. checks.json contains exact commands/results; replay.json and source-bindings.json bind actual retained image metadata and current/before runtime sources. patch.diff contains only the two owned production/test paths.

Run `uv run python -B benchmarks/head-to-head/f05-image-environment-compatibility-20261029/controls.py --output <fresh-output.json>` for the mock replay; run verify.py through uv to check hashes only. Existing historical captures/adapters are immutable and bind older runtime hashes; this new patch does not update or qualify them automatically. Future use needs matching reviewed runtime/config subjects.

This is a compatibility correction, not full task-environment/C1, consumer, oracle or campaign evidence. All actual admission/execution/outcome flags remain false and cost is null. No branch/commit/push or frozen artifact edits by the worker.
