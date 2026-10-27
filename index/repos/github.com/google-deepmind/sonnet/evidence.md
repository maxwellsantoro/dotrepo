# Evidence

- Imported repository name and docs entry points from README.md.
- Inferred repo.test from .github/workflows/ci.yml as `pytest -n auto sonnet --ignore=sonnet/src/conformance/`.
- Imported docs.root as `https://sonnet.readthedocs.io/`. Explicit documentation link at README.md:5: [**Documentation**](https://sonnet.readthedocs.io/) | [**Examples**](#examples)
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
