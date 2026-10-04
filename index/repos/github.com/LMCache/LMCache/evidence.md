# Evidence

- Imported repository docs entry points from README.md.
- Imported maintainer candidates from CODEOWNERS.
- Imported the security reporting channel from SECURITY.md.
- Inferred fallback values for `repo.name` because the imported files did not provide enough structured metadata.
- Inferred repo.build from pyproject.toml as `python -m build`.
- Imported repo.test from CONTRIBUTING.md as `pytest -xvs --ignore=tests/disagg \`.
- Imported repo.toolchain.min from pyproject.toml as `3.10` (Python).
- Discovered related relation to github.com/LMCache/LMCache from README cross-link.
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

- Withheld `repo.test` previously extracted from `CONTRIBUTING.md` as `pytest -xvs --ignore=tests/disagg \`. Command is an incomplete example or setup-only step.
