# Evidence

- Imported repository name from README.md.
- Inferred repo.build from pyproject.toml as `python -m build`.
- Left `repo.test` unset because `.github/workflows/compiler_sanitizers.yml` and `.github/workflows/cygwin.yml` suggested conflicting test commands.
- Imported repo.toolchain.min from pyproject.toml as `3.12` (Python).
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.name` to `numpy` from `GitHub API` after deterministic escalation.
- Set `repo.test` to `python -m pytest` from `pyproject.toml` after deterministic escalation.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Downgrade guard

A prior verified status was preserved because no previously present field regressed in this refresh.
