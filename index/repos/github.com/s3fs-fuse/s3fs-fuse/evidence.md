# Evidence

- Imported repository name from README.md.
- Inferred fallback values for `repo.description` because the imported files did not provide enough structured metadata.
- Left `repo.build` unset because `.github/workflows/ci.yml` suggested an unsafe shell-like command.
- Inferred repo.test from .github/workflows/ci.yml as `make check -C src`.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Filled repo.description from GitHub repository metadata when the README surface did not provide one.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
