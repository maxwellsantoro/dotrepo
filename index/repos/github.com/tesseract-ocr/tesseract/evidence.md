# Evidence

- Imported repository name and docs entry points from README.md.
- Left `repo.build` unset because `.github/workflows/cmake-win64.yml`, `.github/workflows/cmake.yml`, and `.github/workflows/codeql-analysis.yml` suggested conflicting build commands.
- Inferred repo.test from .github/workflows/autotools-macos.yml as `make check`.
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.build` to `cmake --build build --config Release --target install` from `.github/workflows/cmake.yml` after model escalation.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Auto-promotion

Record auto-promoted to verified: all fields are honestly resolved by deterministic promotion scoring.
