# Evidence

- Imported repository name and description from README.md.
- Imported maintainer candidates from CODEOWNERS.
- Left `repo.build` unset because `.github/workflows/deploy-to-github-pages.yml` suggested an unsafe shell-like command.
- Inferred repo.test from .github/workflows/test.yml as `make test`.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Auto-promotion

Record auto-promoted to verified: all fields are honestly resolved by deterministic promotion scoring.
