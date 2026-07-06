# Evidence

- Imported repository name and docs entry points from README.md.
- Inferred repo.build from .github/workflows/index-io-backward-compatibility.yml as `echo "Files created by CMake build:"`.
- Left `repo.test` unset because `.github/workflows/build-pull-request.yml` suggested an unsafe shell-like command.
- Imported repo.toolchain.min from pyproject.toml as `3.10` (Python).
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.test` to `python -m pytest` from `pyproject.toml` after deterministic escalation.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Downgrade guard

A prior verified status was preserved because no previously present field regressed in this refresh.
