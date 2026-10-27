# Evidence

- Imported repository docs entry points from README.md.
- Imported maintainer candidates from CODEOWNERS.
- Inferred fallback values for `repo.name` because the imported files did not provide enough structured metadata.
- Inferred repo.build from pyproject.toml as `python -m build`.
- Imported repo.test from tox.ini as `tox`.
- Imported repo.toolchain.min from pyproject.toml as `3.10` (Python).
- Imported docs.root as `https://supervision.roboflow.com/`. Explicit documentation link at README.md:265: Visit our [documentation](https://supervision.roboflow.com/) page to learn how supervision can help you build computer vision applications faster and more reliably.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
