# Contributing to RIES-RS

This file covers local development expectations and the checks that matter for
the repository's public release surfaces.

## Source of Truth

- `src/`: runtime behavior
- `tests/`: regression expectations
- `README.md`: user-facing overview
- `docs/README.md`: map of current docs vs archived material
- `RELEASING.md`: maintainer release checklist

When docs and code diverge, code and tests win.

## Development Setup

### Required tooling

- Rust stable via [rustup](https://rustup.rs/)
- For `highprec`: GMP and MPFR
  - Ubuntu/Debian: `sudo apt-get install libgmp-dev libmpfr-dev`
  - macOS: `brew install gmp mpfr`
- For Python bindings: Python, [`uv`](https://docs.astral.sh/uv/) (environment
  management), and `maturin` (extension build). `scripts/test_ries_py_python.sh`
  uses `uv` to create the isolated test environment.
- For web/WASM work: Node.js and Rust nightly

### Common build commands

```bash
# Core crate / CLI
cargo build

# Optional features
cargo build --all-features

# Python bindings
cargo check --manifest-path ries-py/Cargo.toml --locked
./scripts/test_ries_py_rust.sh

# WASM feature surface
cargo build --features wasm --locked
```

If you are actively iterating on the Python package:

```bash
cd ries-py
maturin develop --release
```

For reliable Rust-side `ries-py` tests, use a supported interpreter version in
CI and run the helper from the repo root:

```bash
./scripts/test_ries_py_rust.sh
./scripts/test_ries_py_python.sh -q
```

## Verification

Match the CI surfaces relevant to your change.

Core Rust checks:

```bash
cargo fmt --all -- --check
cargo clippy --all-targets --locked -- -D warnings
cargo clippy --all-targets --no-default-features --locked -- -D warnings
cargo nextest run --tests --locked
```

Feature and packaging checks:

```bash
cargo clippy --all-targets --features highprec --locked -- -D warnings
cargo check --manifest-path ries-py/Cargo.toml --locked
./scripts/test_ries_py_rust.sh
./scripts/test_ries_py_python.sh -q
cargo build --features wasm --locked
```

Web UI smoke test when touching `web/`, `src/wasm.rs`, or packaging:

```bash
npm install
npm run test:web:smoke:build
```

## Project Layout

- `src/`: engine, CLI layer, reporting, presets, stability, PSLQ, WASM bindings
- `tests/`: CLI regressions, integration tests, property tests, and web smoke test
- `ries-py/`: Python extension crate and PyPI packaging metadata
- `web/`: browser UI
- `docs/`: current docs plus archived historical material
- `.github/workflows/`: CI, release, coverage, and benchmark automation

See `docs/ARCHITECTURE.md` for a more complete architectural overview.

## Conventions

1. Public APIs and externally visible behavior changes should come with docs updates.
2. New runtime behavior should come with regression coverage.
3. Avoid changing release-surface metadata casually; keep versions and packaging docs in sync.
4. Prefer small, reviewable commits with clear messages.

## Pull Requests

Before opening a PR, confirm the relevant checks above and call out any skipped
surface explicitly in the PR description.

If your change affects a public interface, update the matching docs:

- CLI/library behavior: `README.md`, `docs/SEARCH_MODEL.md`, `docs/ARCHITECTURE.md`
- Python API: `docs/PYTHON_BINDINGS.md`
- WASM/browser surface: `docs/WASM_BINDINGS.md`, `web/README.md`
- release process or artifacts: `RELEASING.md`, `docs/releases/`, `CHANGELOG.md`
