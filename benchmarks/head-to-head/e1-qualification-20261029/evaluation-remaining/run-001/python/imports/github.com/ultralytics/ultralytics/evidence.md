# Evidence

- Imported repository name and description from README.md.
- Inferred repo.build from pyproject.toml as `python -m build`.
- Inferred repo.test from .github/workflows/ci.yml as `pytest $xdist --cov=ultralytics/ --cov-report=xml tests/ --export-env base`.
- Imported repo.toolchain.min from pyproject.toml as `3.8` (Python).
- Discovered related relation to github.com/ultralytics/ultralytics from README cross-link.
- This is an overlay record, not a maintainer-controlled canonical record.
