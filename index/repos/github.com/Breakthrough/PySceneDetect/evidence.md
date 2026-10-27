# Evidence

- Imported repository name and docs entry points from README.md.
- Inferred repo.build from pyproject.toml as `python -m build`.
- Inferred repo.test from .github/workflows/build-windows.yml as `python -m pytest -vv`.
- Imported repo.toolchain.min from pyproject.toml as `3.10` (Python).
- Imported docs.root as `https://www.scenedetect.com/docs/`. Explicit documentation link at README.md:22: **Documentation**:  [scenedetect.com/docs/](https://www.scenedetect.com/docs/)
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
