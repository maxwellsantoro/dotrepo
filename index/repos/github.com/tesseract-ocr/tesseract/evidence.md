# Evidence

- Imported repository name, description, and docs entry points from README.md.
- Left `repo.build` unset because `.github/workflows/cmake-win64.yml`, `.github/workflows/cmake.yml`, and `.github/workflows/codeql-analysis.yml` suggested conflicting build commands.
- Inferred repo.test from .github/workflows/autotools-macos.yml as `make check`.
- This is an overlay record, not a maintainer-controlled canonical record.

- Left `repo.build` unset after deterministic escalation: no unique build/test candidate after deterministic tier walk.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
