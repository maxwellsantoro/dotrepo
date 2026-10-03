# Evidence

- Imported repository name and docs entry points from README.md.
- Imported the security reporting channel from SECURITY.md. SECURITY.md provided a policy or reporting URL rather than a direct mailbox, so `security_contact` preserves that URL.
- Inferred repo.build from .github/workflows/build-dev-binaries.yml as `cargo build --profile no-debug-nightly -Z checksum-freshness`.
- Imported repo.test from CONTRIBUTING.md as `cargo nextest run`.
- Imported repo.toolchain.min from Cargo.toml as `1.96.0` (Rust).
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Documentation correction (2026-09-21T04:36:55.205964Z)

- Corrected evidence for docs.root as `https://docs.astral.sh/uv`: Trio benchmark caption link is not uv documentation. Source: [README.md:81](https://github.com/astral-sh/uv/blob/a5a0b62c4912157bf5e8802453588ef6c0be5a88/README.md#L81).
- Corrected evidence for docs.getting_started as `https://docs.astral.sh/uv/getting-started/installation/`: retain the explicitly declared uv installation documentation. Source: [README.md:76](https://github.com/astral-sh/uv/blob/a5a0b62c4912157bf5e8802453588ef6c0be5a88/README.md#L76).
- This documentation-only correction advances the record timestamp. Older assessments for other fields retain their original check times and are invalidated by public export until fresh verification; their values were not refreshed.
- This is an overlay record, not a maintainer-controlled canonical record.
