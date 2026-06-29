# Evidence

- Imported repository name and description from README.md.
- Left `repo.build` unset because `package.json` and `pyproject.toml` suggested conflicting build commands.
- Imported repo.test from pyproject.toml as `python -m pytest`.
- This is an overlay record, not a maintainer-controlled canonical record.

- Left `repo.build` unset after deterministic escalation: no unique build/test candidate after deterministic tier walk.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
