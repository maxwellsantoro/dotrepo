# Evidence

- Imported repository name, description, and docs entry points from README.md.
- Imported maintainer candidates from CODEOWNERS. Maintainer information was imported from broad CODEOWNERS patterns; `owners.team` prefers `@eslint/eslint-team` from the repo-wide rule, and `owners.maintainers` preserves narrower owner candidates.
- Left `repo.build` unset because `.github/workflows/docs-ci.yml`, `.github/workflows/types-integration.yml`, and `.github/workflows/update-readme.yml` suggested conflicting build commands.
- Left `repo.test` unset because `.github/workflows/ci.yml`, `.github/workflows/types-integration.yml`, and `package.json` suggested conflicting test commands.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
