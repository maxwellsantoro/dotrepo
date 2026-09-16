# Evidence

- Imported repository name and docs entry points from README.md.
- Imported maintainer candidates from CODEOWNERS.
- Inferred repo.build from libs/core/pyproject.toml as `python -m build`.
- Left `repo.test` unset because `.github/workflows/_compile_integration_test.yml`, `.github/workflows/_test.yml`, and `.github/workflows/_test_pydantic.yml` suggested conflicting test commands.
- Imported repo.toolchain.min from libs/core/pyproject.toml as `3.10.0` (Python).
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.name` to `langchain` from `GitHub API` after deterministic escalation.
- Set `repo.test` to `python -m pytest` from `libs/core/pyproject.toml` after deterministic escalation.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Fresh verification

Prior verified authority was not inherited: this refresh must qualify using its current field scores.
