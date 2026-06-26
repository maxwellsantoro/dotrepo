# Evidence

- Imported repository name, description, and docs entry points from README.md.
- Left `repo.build` unset because `package.json` and `pyproject.toml` suggested conflicting build commands.
- Imported repo.test from pyproject.toml as `python -m pytest`.
- This is an overlay record, not a maintainer-controlled canonical record.

- Left `repo.build` unset after model escalation: The candidates represent two distinct technology stacks (Node.js and Python) with no indication of which one is the primary language of the repository. Since no single primary value can be determined, null is returned..
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
