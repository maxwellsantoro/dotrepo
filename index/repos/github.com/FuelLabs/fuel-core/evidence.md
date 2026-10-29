# Evidence

- Imported repository name and docs entry points from README.md.
- Imported maintainer candidates from CODEOWNERS. Maintainer information was imported from broad CODEOWNERS patterns with multiple team owners, so `owners.team` was left unset and `owners.maintainers` preserves the competing owner candidates.
- Imported the security reporting channel from SECURITY.md. SECURITY.md provided a policy or reporting URL rather than a direct mailbox, so `security_contact` preserves that URL.
- Imported repo.build from CONTRIBUTING.md as `cargo build -p fuel-core-bin --no-default-features`.
- Imported repo.test from CONTRIBUTING.md as `cargo test --all-targets`.
- Imported repo.toolchain.min from Cargo.toml as `1.94.1` (Rust).
- Imported docs.root as `https://docs.rs/fuel-core/`. Explicit documentation link at README.md:6: [![docs](https://docs.rs/fuel-core/badge.svg)](https://docs.rs/fuel-core/)
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.name` to `fuel-core` from `GitHub API` after deterministic escalation.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Auto-promotion

All fields are high-confidence present or high-confidence absent. Record auto-promoted to verified status.


## Partial command-scope correction — October 28, 2026

The earlier extraction and auto-promotion notes above are historical. The following scalar answers are withheld after inspection at the recorded upstream revision:

- `repo.build`: Package-specific build with disabled defaults in the Build issues troubleshooting section.

Record status is now imported with medium record confidence. This is a partial source inspection, not a full-record re-verification or upstream execution. Record age, GitHub metadata, unrelated fields and their assessments are unchanged. New null assessments are checked at 2026-10-29T02:06:09.861151Z; because they are newer than the record timestamp, the public exporter withholds them until a coherent record refresh. See `index/telemetry/public-surface-review-20261028/command-scope-corrections.json`.
