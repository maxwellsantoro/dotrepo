# ries-rs

Rust inverse equation solver for turning a target number into compact algebraic equations.

[![CI](https://github.com/maxwellsantoro/ries-rs/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/maxwellsantoro/ries-rs/actions/workflows/ci.yml)
[![Coverage](https://github.com/maxwellsantoro/ries-rs/actions/workflows/coverage.yml/badge.svg?branch=main)](https://github.com/maxwellsantoro/ries-rs/actions/workflows/coverage.yml)
[![Live Demo](https://img.shields.io/badge/live-demo-0f766e)](https://maxwellsantoro.com/projects/ries-rs/app/)
[![Crates.io](https://img.shields.io/crates/v/ries.svg)](https://crates.io/crates/ries)
[![PyPI](https://img.shields.io/pypi/v/ries-rs.svg?cacheSeconds=300)](https://pypi.org/project/ries-rs/)
[![DOI](https://zenodo.org/badge/1123876688.svg)](https://doi.org/10.5281/zenodo.19101924)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

`ries-rs` is a Rust implementation of Robert P. Munafo's RIES inverse equation
solver. Given a target number, it searches for algebraic equations that have
that number as a solution.

The historical acronym is RIES, for "RILYBOT Inverse Equation Solver". This
repository aims to be a modern, documented, reproducible reference
implementation rather than a historical clone.

> **Name map:** crates.io crate `ries`; installed CLI `ries-rs`; PyPI package
> `ries-rs`; Python import `ries_rs`.

Project page: [maxwellsantoro.com/projects/ries-rs](https://maxwellsantoro.com/projects/ries-rs)  
Live demo: [maxwellsantoro.com/projects/ries-rs/app/](https://maxwellsantoro.com/projects/ries-rs/app/)

![RIES-RS web UI](docs/assets/web-ui.png)

## Who It's For

- Researchers who want reproducible constant-recognition runs with structured output and run manifests
- Programmers who want equation search embedded in Rust, Python, or browser workflows
- People comparing modern behavior against historical RIES baselines with explicit parity notes
- Educators and demo authors who want the same engine behind a CLI, Python module, and live browser demo

## Why Use `ries-rs`

- Rust implementation with a cleaner architecture and broad regression coverage
- Deterministic mode for reproducible output ordering
- Structured JSON and manifests for automation and research workflows
- Browser and library integrations in addition to the CLI
- Public benchmark artifacts and explicit parity tracking against older versions

## Install

### CLI

Use `cargo install ries --locked` to install the `ries-rs` executable.

```bash
cargo install ries --locked
```

Prebuilt Linux, macOS, and Windows archives are attached to each
[GitHub release](https://github.com/maxwellsantoro/ries-rs/releases).

For unreleased development builds:

```bash
cargo install --git https://github.com/maxwellsantoro/ries-rs --locked

# Or, from a local checkout:
cargo install --path . --locked
```

### Python Bindings

```bash
pip install ries-rs
```

For local source development of the bindings:

```bash
uv venv
source .venv/bin/activate
uv pip install maturin
cd ries-py
maturin develop --release
```

For Rust-side binding checks without building/loading the extension module:

```bash
./scripts/test_ries_py_rust.sh
```

For end-to-end Python import/search checks in an isolated virtualenv:

```bash
./scripts/test_ries_py_python.sh -q
```

### Web App / WASM

GitHub releases include a `ries-rs-wasm.tar.gz` artifact with the generated WASM
packages. To build the browser bundle locally, install the JS dependencies and
the nightly Rust toolchain first:

```bash
npm install
rustup toolchain install nightly
npm run build:web:site
```

Deploy the contents of `dist/web-site/` to a path such as
`https://example.com/projects/ries-rs/`.

The current local WASM build scripts use nightly `wasm-pack` via `-Z build-std`.

For the public deployment, use the canonical landing page at
`https://maxwellsantoro.com/projects/ries-rs` and the standalone app at
`https://maxwellsantoro.com/projects/ries-rs/app/`.

Detailed setup guides:

- [Python bindings](docs/PYTHON_BINDINGS.md)
- [WASM bindings](docs/WASM_BINDINGS.md)
- [Web UI hosting](web/README.md)

## Quick Start

Basic search:

```bash
ries-rs 3.141592653589793
```

Example output:

```text
                       x = pi                       ('exact' match) {29}
                      -x = -pi                      ('exact' match) {43}
                     1/x = 1/pi                     ('exact' match) {43}
```

Classic-style output:

```bash
ries-rs --classic 2.5063
```

Deterministic machine-readable output:

```bash
ries-rs 3.141592653589793 --deterministic --json --emit-manifest run.json
```

Turbo mode (parallelize matching across all cores for maximum speed):

```bash
ries-rs 2.506314 -l3 --turbo
```

`--turbo` runs the match/Newton phase on every core. It returns the same single
best match as the serial path but trades reproducibility and memory for speed —
the lower-ranked tail may differ between runs and thread counts. Use
`--deterministic` instead when you need reproducible output.

For the authoritative option list:

```bash
ries-rs --help
```

## Project Scope

`ries-rs` is intended to be a disciplined, modern reference implementation:

- Faithful reimplementation of the core RIES search model
- Deterministic and documented execution modes
- Memory-safe Rust implementation with optional parallel generation and a
  parallel `--turbo` match phase
- Structured output for automation (`--json`, `--emit-manifest`)
- CLI, Rust library, Python bindings, and WebAssembly builds
- Modular presets, profiles, and extension points

Not primary goals of this repository:

- Symbolic AI or conjecture systems
- Turning the bundled PSLQ integer-relation mode into a separate research platform
- Experimental search branches outside the core RIES model

## Performance

Performance claims are tracked conservatively with separate benchmark artifacts
for end-to-end CLI runs and generation-only scaling:

- End-to-end CLI baseline:
  [`docs/benchmarks/2026-03-20-level3-baseline.md`](docs/benchmarks/2026-03-20-level3-baseline.md)
  captures the current level-3 workload; after tightening the adaptive search
  radius and snapping exact default-scale trig singularities, the candidate
  scan set dropped to about `8.1M` pairs. The default `--parallel` CLI path is
  near break-even on this workload because it parallelizes generation only,
  while the dominant matching/Newton phase stays serial to preserve
  byte-identical results.
- `--turbo` parallelizes the matching/Newton phase itself, trading the
  byte-identical guarantee (and extra memory) for large end-to-end speedups on
  multi-core machines — measured `4x`–`35x` over the serial path on level-3
  targets (8 cores). It still returns the same single best match as serial; see
  [`docs/SEARCH_MODEL.md`](docs/SEARCH_MODEL.md) for the turbo contract.
- Generation-only scaling:
  [`docs/benchmarks/2026-02-25-generation-parallel-scaling.md`](docs/benchmarks/2026-02-25-generation-parallel-scaling.md)
  reports `3.18x` median speedup for parallel generation.

Raw benchmark artifacts live under `docs/benchmarks/artifacts/`.

## Compatibility

`ries-rs` tracks behavior against two historical baselines while keeping a
Rust-native engine and build surface:

1. The original RIES by Robert Munafo
2. The `clsn/ries` fork with additional compatibility-oriented CLI behavior

Current status in brief:

- Core equation search and classic-style output flow are implemented
- Legacy CLI semantics and diagnostic channels are supported substantially more
  completely than in early versions
- The Rust-native engine keeps modern build and integration advantages, while
  edge-case ordering or complexity scores can still differ from historical
  binaries on some targets

See [`docs/PARITY_STATUS.md`](docs/PARITY_STATUS.md) for the detailed status and
historical notes.

## How It Works

1. Enumerate valid postfix expressions up to the current complexity limit
2. Check fast-path exact matches against well-known constants when possible
3. Generate left-hand-side and right-hand-side expression candidates
4. Use Newton refinement to solve `LHS(x) = RHS`
5. Filter, deduplicate, and refine candidate equations
6. Rank matches by exactness, then error (exact matches rank by simplicity, not
   sub-tolerance residual), then parity-style or complexity-style order

## Documentation

- [Documentation map](docs/README.md)
- [Search model](docs/SEARCH_MODEL.md)
- [Complexity and weights](docs/COMPLEXITY.md)
- [Architecture overview](docs/ARCHITECTURE.md)
- [Performance notes and benchmarks](docs/PERFORMANCE.md)
- [Parity and compatibility status](docs/PARITY_STATUS.md)
- [Python bindings](docs/PYTHON_BINDINGS.md)
- [WASM bindings](docs/WASM_BINDINGS.md)
- [Web UI build and hosting](web/README.md)

## Contributing

If you want to improve the engine, docs, packaging, or release surfaces, start
with [CONTRIBUTING.md](CONTRIBUTING.md) for setup and verification expectations.

## Additional Interfaces

### Python

The Python bindings expose `ries_rs.search()` and typed match objects through
PyO3. See [docs/PYTHON_BINDINGS.md](docs/PYTHON_BINDINGS.md) for PyPI install,
source development, API details, and troubleshooting.

### WebAssembly

The WASM build supports browser, Node.js, bundler, and static-site workflows.
See [docs/WASM_BINDINGS.md](docs/WASM_BINDINGS.md) for the JS/TS API and
[web/README.md](web/README.md) for the browser UI and static hosting flow.

### PSLQ

The CLI includes PSLQ integer-relation detection via `--pslq`,
`--pslq-extended`, and `--pslq-max-coeff`. This is part of the shipped tool,
but it is not the primary focus of the repository.

## How to Cite

If you use `ries-rs` in academic work, cite the project version you used.
`CITATION.cff` is the canonical metadata source.

```bibtex
@software{ries-rs2026,
  author       = {Santoro, Maxwell},
  title        = {ries-rs: A Rust Implementation of the RIES Inverse Equation Solver},
  year         = {2026},
  version      = {2.0.2},
  url          = {https://maxwellsantoro.com/projects/ries-rs},
  license      = {MIT},
  note         = {Features parallel search, deterministic mode, and run manifest for reproducibility}
}
```

Zenodo concept DOI for the project and its archived releases:
`10.5281/zenodo.19101924`

The latest verified version DOI is for `v1.1.1`:
`10.5281/zenodo.19101925`

No version DOI is recorded for `v2.0.2` until its Zenodo archive has completed.

Use the concept DOI when you want a stable project-level reference that resolves
to the latest archived release. Use the version DOI when you need to cite the
specific archived release you used.

For reproducible research runs, prefer `--deterministic` together with
`--emit-manifest`.

When `--emit-manifest` is requested, failure to serialize or write the manifest
prints an error and exits nonzero. A parent directory must already exist, and
the destination must be a writable file path.

Manifests summarize the supported run configuration and results; they are not a
full source-bound replay or build attestation for every custom or profile option.

## License

MIT License. See [`LICENSE`](LICENSE).

## References

- [Original RIES](https://mrob.com/pub/ries/) by Robert Munafo
- [RIES Documentation](https://mrob.com/pub/ries/ries.html)
- [`clsn/ries` fork](https://github.com/clsn/ries)
- Stoutemyer, D.R. (2024). "Computing with No Machine Constants, Only
  Constructive Axioms". arXiv:2402.03304
