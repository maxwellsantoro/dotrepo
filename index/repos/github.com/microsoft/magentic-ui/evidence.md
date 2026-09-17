# Evidence

- Imported repository name and docs entry points from README.md.
- Imported the security reporting channel from SECURITY.md.
- Inferred repo.build from pyproject.toml as `python -m build`.
- Inferred repo.test from .github/workflows/checks.yaml as `pytest tests --cov=src --cov-report=xml --cov-report=term-missing`.
- Imported repo.toolchain.min from pyproject.toml as `3.12` (Python).
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.name` to `magentic-ui` from `GitHub API` after deterministic escalation.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
