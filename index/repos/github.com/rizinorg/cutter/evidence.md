# Evidence

- Imported repository name and description from README.md.
- Imported the security reporting channel from SECURITY.md.
- Left `repo.build` unset because `.github/workflows/ci.yml` suggested an unsafe shell-like command.
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.build` to `cmake -S . -B build \` from `.github/workflows/linter.yml` after deterministic escalation.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
