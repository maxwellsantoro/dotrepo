# Evidence

- Imported repository name and docs entry points from README.md.
- Imported the security reporting channel from SECURITY.md. SECURITY.md provided a policy or reporting URL rather than a direct mailbox, so `security_contact` preserves that URL.
- Ignored component-scoped commands from `frontend/taipy-gui/package.json` as repository defaults.
- Ignored component-scoped commands from `taipy/common/setup.py` as repository defaults.
- Inferred repo.build from pyproject.toml as `python -m build`.
- Inferred repo.test from pyproject.toml as `python -m pytest`.
- Imported repo.toolchain.min from pyproject.toml as `3.9` (Python).
- Imported docs.root as `https://docs.taipy.io/en/latest/`. Explicit documentation link at README.md:124: [Taipy Documentation](https://docs.taipy.io/en/latest/) to help you with Taipy tools.
- Conflicting documentation declarations in README.md; abstained from docs.getting_started.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
