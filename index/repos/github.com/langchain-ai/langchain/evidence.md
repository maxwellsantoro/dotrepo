# Evidence

- Imported repository name, description, and docs entry points from README.md.
- Imported maintainer candidates from CODEOWNERS.
- Inferred repo.build from .github/workflows/_compile_integration_test.yml as `uv run pytest -m compile tests/integration_tests`.
- Left `repo.test` unset because `.github/workflows/_compile_integration_test.yml`, `.github/workflows/_lint.yml`, `.github/workflows/_release.yml`, `.github/workflows/_test.yml`, `.github/workflows/_test_pydantic.yml`, and `.github/workflows/_test_vcr.yml` suggested conflicting test commands.
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.test` to `make test PYTEST_EXTRA=-q` from `.github/workflows/_test.yml` after model escalation.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
