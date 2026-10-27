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
