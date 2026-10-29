# Evidence

- Imported repository name from README.md.
- Inferred repo.build from Cargo.toml as `cargo build --workspace`.
- Imported repo.test from CONTRIBUTING.md as `cargo test --features debug`.
- Imported repo.toolchain.min from Cargo.toml as `1.85` (Rust).
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

- `repo.test`: Debug-output diagnostic invocation, not the selected repository-default test procedure.

Record status is now imported with medium record confidence. This is a partial source inspection, not a full-record re-verification or upstream execution. Record age, GitHub metadata, unrelated fields and their assessments are unchanged. New null assessments are checked at 2026-10-29T02:06:09.861151Z; because they are newer than the record timestamp, the public exporter withholds them until a coherent record refresh. See `index/telemetry/public-surface-review-20261028/command-scope-corrections.json`.
