# Evidence

- Imported repository name and docs entry points from README.md.
- Imported the security reporting channel from SECURITY.md. SECURITY.md provided a policy or reporting URL rather than a direct mailbox, so `security_contact` preserves that URL.
- Imported repo.build from CONTRIBUTING.md as `cargo build --target x86_64-unknown-linux-musl --profile profiling`.
- Imported repo.test from CONTRIBUTING.md as `cargo nextest run`.
- Imported repo.toolchain.min from Cargo.toml as `1.97.0` (Rust).
- Imported docs.root as `https://docs.astral.sh/uv`. Explicit documentation link at README.md:81: uv's documentation is available at [docs.astral.sh/uv](https://docs.astral.sh/uv).
- Imported docs.getting_started as `https://docs.astral.sh/uv/getting-started/installation/`. Explicit documentation link at README.md:76: See the [installation documentation](https://docs.astral.sh/uv/getting-started/installation/) for
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
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

- `repo.build`: Docker/musl profiling workflow, not a repository-default build.
- `repo.test`: The source shows a nextest selector example; deleting its filter invented an unfiltered default.

Record status is now imported with medium record confidence. This is a partial source inspection, not a full-record re-verification or upstream execution. Record age, GitHub metadata, unrelated fields and their assessments are unchanged. New null assessments are checked at 2026-10-29T02:06:09.861151Z; because they are newer than the record timestamp, the public exporter withholds them until a coherent record refresh. See `index/telemetry/public-surface-review-20261028/command-scope-corrections.json`.
