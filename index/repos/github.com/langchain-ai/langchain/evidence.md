# Evidence

- Imported repository name and docs entry points from README.md.
- Imported maintainer candidates from CODEOWNERS.
- Inferred repo.build from .github/workflows/_compile_integration_test.yml as `uv run pytest -m compile tests/integration_tests`.
- Left `repo.test` unset because `.github/workflows/_compile_integration_test.yml`, `.github/workflows/_test.yml`, `.github/workflows/_test_pydantic.yml`, and `.github/workflows/_test_vcr.yml` suggested conflicting test commands.
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.name` to `langchain` from `GitHub API` after deterministic escalation.
- Left `repo.test` unset after deterministic escalation: no unique build/test candidate after deterministic tier walk. Preserved 4 candidate command(s) in `repo.test_candidates` instead of discarding them.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
