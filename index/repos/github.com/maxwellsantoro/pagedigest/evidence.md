# Evidence

- Imported repository name from README.md.
- Ignored component-scoped commands from `packages/astro/package.json` as repository defaults.
- Ignored component-scoped commands from `implementations/python-consumer/pyproject.toml` as repository defaults.
- Inferred repo.test from .github/workflows/publish-crate.yml as `cargo test --locked --manifest-path implementations/rust-generator/Cargo.toml`.
- Imported repo.toolchain.min from implementations/python-consumer/pyproject.toml as `3.9` (Python).
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## October 28, 2026 — Cargo command scope correction

Inspected `.github/workflows/publish-crate.yml` at upstream commit
`f880f813cc0df49603482dbd879ff4ef49b3a519`:
https://github.com/maxwellsantoro/pagedigest/blob/f880f813cc0df49603482dbd879ff4ef49b3a519/.github/workflows/publish-crate.yml

The test invocation explicitly selects `implementations/rust-generator/Cargo.toml`.
It checks that component, not the repository's Python consumer and other components.
Removed the scalar `repo.test` and its matching field assessment. The source does
not declare a complete prerequisite/context tuple, so no replacement contextual
assessment is asserted. The record's original generation timestamp and unrelated
assessments are retained; this partial inspection does not refresh the whole record.
The captured source and regression expectation live in the
`command-pagedigest-manifest-path` importer fixture.
