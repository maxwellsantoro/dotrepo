# Evidence

- Imported repository name and docs entry points from README.md.
- Imported maintainer candidates from CODEOWNERS.
- Imported the security reporting channel from SECURITY.md.
- Inferred repo.build from pyproject.toml as `python -m build`.
- Imported repo.test from .github/CONTRIBUTING.md as `python -m pytest tests/.../test_file.py::test_explain_what_is_being_tested -v --capture=no`.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Command semantic correction (2026-10-03)

2026-10-03 semantic audit withheld repo.test pending command context or usable upstream instructions; repository-default applicability remains unresolved. Source inspection timestamps are unchanged.

- Withheld `repo.test` previously extracted from `.github/CONTRIBUTING.md` as `python -m pytest tests/.../test_file.py::test_explain_what_is_being_tested -v --capture=no`. Command is an incomplete example or setup-only step.
