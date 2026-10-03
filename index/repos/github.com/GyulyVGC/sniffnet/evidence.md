# Evidence

- Imported repository name `Sniffnet` from the header image's `title` attribute in [README.md at the recorded HEAD](https://github.com/GyulyVGC/sniffnet/blob/592a62a5ad2fb2e9f8470a6174ab9f18dc86997a/README.md#L3).
- Rechecked `repo.name` on 2026-10-03 against that pinned source. The later support/development heading is a donation call to action, not the project name; no other fields were refreshed.
- Imported the security reporting channel from SECURITY.md.
- Inferred repo.build from .github/workflows/rust.yml as `cargo build --verbose`.
- Inferred repo.test from .github/workflows/rust.yml as `cargo test --verbose -- --nocapture`.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
