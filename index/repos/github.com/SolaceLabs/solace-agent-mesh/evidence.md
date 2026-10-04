# Evidence

- Imported repository name from README.md.
- Inferred fallback values for `repo.description` because the imported files did not provide enough structured metadata.
- Ignored component-scoped commands from `client/webui/frontend/package.json` as repository defaults.
- Inferred repo.build from pyproject.toml as `python -m build`.
- Imported repo.test from README.md as `pytest`.
- Imported repo.toolchain.min from pyproject.toml as `3.10.16` (Python).
- Conflicting documentation declarations in README.md; abstained from docs.root.
- Conflicting documentation declarations in README.md; abstained from docs.getting_started.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
