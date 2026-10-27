# Evidence

- Inferred fallback values for `repo.name` because the imported files did not provide enough structured metadata.
- Inferred repo.build from pyproject.toml as `python -m build`.
- Inferred repo.test from .github/workflows/test.yml as `python -m pytest tests/test_notebook_output_hygiene.py -q`.
- Imported repo.toolchain.min from pyproject.toml as `3.14` (Python).
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
