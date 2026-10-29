# Evidence

- Imported repository name and docs entry points from README.md.
- Imported the security reporting channel from SECURITY.md. SECURITY.md provided a policy or reporting URL rather than a direct mailbox, so `security_contact` preserves that URL.
- Inferred repo.build from Cargo.toml as `cargo build --workspace`.
- Left `repo.test` unset because `Cargo.toml` and `pyproject.toml` suggested conflicting test commands.
- Imported repo.toolchain.min from Cargo.toml as `1.97.0` (Rust).
- Imported docs.root as `https://docs.astral.sh/uv`. Explicit documentation link at README.md:81: uv's documentation is available at [docs.astral.sh/uv](https://docs.astral.sh/uv).
- Imported docs.getting_started as `https://docs.astral.sh/uv/getting-started/installation/`. Explicit documentation link at README.md:76: See the [installation documentation](https://docs.astral.sh/uv/getting-started/installation/) for
- This is an overlay record, not a maintainer-controlled canonical record.

- Left `repo.test` unset after deterministic escalation: no unique build/test candidate after deterministic tier walk. Preserved 2 candidate command(s) in `repo.test_candidates` instead of discarding them.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
