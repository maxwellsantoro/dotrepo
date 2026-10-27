# Evidence

- Imported repository name and docs entry points from README.md.
- Imported maintainer candidates from CODEOWNERS.
- Imported the security reporting channel from SECURITY.md. SECURITY.md provided a policy or reporting URL rather than a direct mailbox, so `security_contact` preserves that URL.
- Inferred repo.build from .github/workflows/publish.yml as `python -m build`.
- Imported repo.test from tox.ini as `tox`.
- Imported repo.toolchain.min from pyproject.toml as `3.10` (Python).
- Imported docs.root as `https://requests.readthedocs.io`. Explicit documentation link at README.md:7: [![Documentation](https://readthedocs.org/projects/requests/badge/?version=latest)](https://requests.readthedocs.io)
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
