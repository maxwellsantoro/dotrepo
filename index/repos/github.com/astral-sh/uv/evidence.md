# Evidence

- Imported repository name, description, and docs entry points from README.md.
- Imported the security reporting channel from SECURITY.md. SECURITY.md provided a policy or reporting URL rather than a direct mailbox, so `security_contact` preserves that URL.
- Inferred repo.build from .github/workflows/bench.yml as `cargo run --bin uv -- pip compile test/requirements/jupyter.in --universal --exclude-newer 2024-08-08 --cache-dir .cache`.
- Left `repo.test` unset because `Cargo.toml` and `pyproject.toml` suggested conflicting test commands.
- Imported repo.toolchain.min from Cargo.toml as `1.94.0` (Rust).
- This is an overlay record, not a maintainer-controlled canonical record.

- Left `repo.test` unset after deterministic escalation: no unique build/test candidate after deterministic tier walk. Preserved 2 candidate command(s) in `repo.test_candidates` instead of discarding them.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
