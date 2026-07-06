# Evidence

- Imported repository name and docs entry points from README.md.
- Inferred repo.build from .github/workflows/python-publish.yml as `python -m build --sdist`.
- Inferred repo.test from .github/workflows/test.yml as `pytest --durations=0 -vv -k 'not test_transcribe or test_transcribe[tiny] or test_transcribe[tiny.en]' -m 'not requires_cuda'`.
- Imported repo.toolchain.min from pyproject.toml as `3.8` (Python).
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Downgrade guard

A prior verified status was preserved because no previously present field regressed in this refresh.
