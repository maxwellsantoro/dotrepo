# Evidence

- Imported the security reporting channel from SECURITY.md.
- Inferred fallback values for `repo.name` and `repo.description` because the imported files did not provide enough structured metadata.
- Imported repo.build from Makefile as `make all`.
- Inferred repo.test from .github/workflows/cuda-ci.yml as `SCIPY_ARRAY_API=1 pytest --doctest-modules modules/array_api.rst`.
- Imported repo.toolchain.min from pyproject.toml as `3.12` (Python).
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
