# Evidence

- Imported repository name from README.md.
- Imported the security reporting channel from SECURITY.md.
- Inferred fallback values for `repo.description` because the imported files did not provide enough structured metadata.
- Inferred repo.build from .github/workflows/ci_macos.yaml as `cmake --build build`.
- Inferred repo.test from .github/workflows/ci_ubuntu.yaml as `cmake --build build --target check`.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Auto-promotion

Record auto-promoted to verified: all fields are honestly resolved by deterministic promotion scoring.
