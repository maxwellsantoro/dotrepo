# Evidence

- Imported repository name, description, and docs entry points from README.md.
- Imported maintainer candidates from CODEOWNERS.
- Imported repo.build from pyproject.toml as `python -m build`.
- Left `repo.test` unset because `pyproject.toml` and `.github/workflows/code-checks.yml` suggested conflicting test commands.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
