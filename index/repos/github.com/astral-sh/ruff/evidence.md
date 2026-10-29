# Evidence

- Imported repository name and docs entry points from README.md.
- Imported maintainer candidates from CODEOWNERS. Maintainer information was imported from broad CODEOWNERS patterns with multiple team owners, so `owners.team` was left unset and `owners.maintainers` preserves the competing owner candidates.
- Ignored component-scoped commands from `playground/ruff/package.json` as repository defaults.
- Inferred repo.build from Cargo.toml as `cargo build --workspace`.
- Imported repo.test from CONTRIBUTING.md as `cargo test -p ruff_python_parser`.
- Imported repo.toolchain.min from Cargo.toml as `1.97` (Rust).
- Imported docs.root as `https://docs.astral.sh/ruff/`. Explicit documentation link at README.md:12: [**Docs**](https://docs.astral.sh/ruff/) | [**Playground**](https://play.ruff.rs/)
- Discovered related relation to github.com/astral-sh/ruff from README cross-link.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).


## Partial command-scope correction — October 28, 2026

The earlier extraction and auto-promotion notes above are historical. The following scalar answers are withheld after inspection at the recorded upstream revision:

- `repo.test`: Parser-package tests in a Unicode update workflow, not repository-wide tests.

Record status is now imported with medium record confidence. This is a partial source inspection, not a full-record re-verification or upstream execution. Record age, GitHub metadata, unrelated fields and their assessments are unchanged. New null assessments are checked at 2026-10-29T02:06:09.861151Z; because they are newer than the record timestamp, the public exporter withholds them until a coherent record refresh. See `index/telemetry/public-surface-review-20261028/command-scope-corrections.json`.
