# Evidence

- Imported repository name and docs entry points from README.md.
- Imported maintainer candidates from CODEOWNERS.
- Imported the security reporting channel from SECURITY.md. SECURITY.md provided a policy or reporting URL rather than a direct mailbox, so `security_contact` preserves that URL.
- Left `repo.build` unset because `.github/workflows/js-and-wasm-artifacts.yml` and `.github/workflows/lagom-template.yml` suggested conflicting build commands.
- Inferred repo.test from Cargo.toml as `cargo test --workspace`.
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.build` to `-DCMAKE_C_COMPILER=clang \` from `.github/workflows/js-and-wasm-artifacts.yml` after deterministic escalation.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
