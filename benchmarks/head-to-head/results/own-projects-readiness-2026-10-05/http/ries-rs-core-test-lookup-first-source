# AGENTS.md

Guidance for AI coding agents working in `ries-rs`. Humans should read
`README.md` and `CONTRIBUTING.md`; this file is the fast-path orientation for
agents.

## What this project is

A Rust reimplementation of Robert Munafo's RIES inverse equation solver: given a
target number, it searches for compact algebraic equations that have that number
as a solution. The same engine ships through four surfaces:

- **Rust CLI** — `src/main.rs` (installed binary `ries-rs`, crate `ries`)
- **Rust library** — `src/lib.rs`
- **Python bindings** — `ries-py/` (PyO3, PyPI package `ries-rs`, import `ries_rs`)
- **WASM + browser UI** — `src/wasm.rs`, `web/`, `package.json`

All four feed the same core generation / evaluation / ranking / reporting logic
in `src/`. See `docs/ARCHITECTURE.md` for the full map and `docs/SEARCH_MODEL.md`
for the formal search and determinism contract.

## Source-of-truth rule

When docs and code disagree, **code and tests win**. `docs/archive/` is
historical context only — never treat it as current behavior.

- `src/` owns runtime behavior
- `tests/` owns regression and compatibility expectations
- `README.md` / `docs/` explain the public surfaces
- `RELEASING.md` is the maintainer release checklist

## Verify your changes

Match the CI surfaces relevant to what you touched (full list in
`CONTRIBUTING.md`). Core Rust loop:

```bash
cargo fmt --all -- --check
cargo clippy --all-targets --locked -- -D warnings
cargo nextest run --tests --locked   # or: cargo test
```

Feature / binding / packaging surfaces, when relevant:

```bash
cargo clippy --all-targets --no-default-features --locked -- -D warnings
cargo clippy --all-targets --features highprec --locked -- -D warnings
cargo build --features wasm --locked
cargo check --manifest-path ries-py/Cargo.toml --locked
./scripts/test_ries_py_rust.sh          # Rust-side binding tests
./scripts/test_ries_py_python.sh -q     # end-to-end Python import/search (uses uv)
```

CI (`.github/workflows/ci.yml`) is the authoritative gate: dotrepo manifest
validation, release-integrity, fmt, clippy across feature sets, both binding
test paths, and `cargo nextest` on Linux/macOS/Windows.

## Conventions

1. `highprec` needs system GMP/MPFR (`brew install gmp mpfr` /
   `apt-get install libgmp-dev libmpfr-dev`); WASM work needs Node.js + Rust
   nightly.
2. Python tooling uses `uv` for environments and `maturin` to build the
   extension — do not introduce ad-hoc `venv`/`pip` flows or `requirements.txt`.
3. Determinism is part of the contract: canonical ordering lives in
   `src/pool.rs`, complexity weights in `src/symbol.rs` / `src/symbol_table.rs`.
   Prefer `--deterministic` (+ `--emit-manifest`) for reproducible runs.
4. New runtime behavior ships with regression coverage; public-interface changes
   ship with matching docs updates (see `CONTRIBUTING.md` for the doc map).
5. The bundled PSLQ mode (`--pslq*`) is a shipped feature, not the project's
   focus — keep it scoped.
6. Keep release-surface metadata (versions, packaging docs) in sync; don't change
   it casually.

## Registry

This project is registered in the portfolio registry as `RIES`
(`~/projects/registry/project_registry.json`, family `formal-math`). Update the registry
entry there rather than describing project metadata only in code.
