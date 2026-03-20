# Evidence

- Imported repository name and description from README.md after stripping trailing badge markup and reference-definition lines.
- Imported `docs.root = "https://serde.rs/"` and `docs.getting_started = "https://serde.rs/derive.html"` from the README's "You may be looking for" links, and `docs.api = "https://docs.rs/serde/latest/serde/"` from the same upstream docs surface.
- Imported `repo.build = "cd serde && cargo build"` from the CI workflow's nightly build lane, which exercises the primary crate directly from the repository root checkout.
- Imported `repo.test = "cd test_suite && cargo +nightly test --features unstable"` from CONTRIBUTING.md, which documents the full nightly-only test suite for contributors.
- Imported `repo.license = "MIT OR Apache-2.0"` from `serde/Cargo.toml`; GitHub's repository metadata only exposes one side of the dual license, so the package manifest is the stronger source here.
- No SECURITY.md or CODEOWNERS file was detected in the repository snapshot used for this overlay, so `owners.security_contact` and maintainer ownership fields remain intentionally unset.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
