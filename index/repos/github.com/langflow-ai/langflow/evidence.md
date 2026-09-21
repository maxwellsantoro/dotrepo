# Evidence

- Imported repository name and docs entry points from README.md.
- Imported the security reporting channel from SECURITY.md. SECURITY.md provided a policy or reporting URL rather than a direct mailbox, so `security_contact` preserves that URL.
- Imported repo.build from docs/package.json as `npm run build`.
- Inferred repo.test from .github/workflows/ci.yml as `uv run pytest src/backend/tests/unit/template/test_starter_projects.py -v -n auto`.
- Imported repo.toolchain.min from pyproject.toml as `3.10` (Python).
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.name` to `langflow` from `GitHub API` after deterministic escalation.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Documentation correction (2026-09-21T04:36:55.205964Z)

- Corrected evidence for docs.getting_started as `https://docs.langflow.org/get-started-installation#install-and-run-the-langflow-oss-python-package`: uv package-manager installation is not Langflow installation documentation. Source: [README.md:50](https://github.com/langflow-ai/langflow/blob/5621dcfd84e11108e4cc1ecb0c51f41053c4211c/README.md#L50).
- This documentation-only correction advances the record timestamp. Older assessments for other fields retain their original check times and are invalidated by public export until fresh verification; their values were not refreshed.
- This is an overlay record, not a maintainer-controlled canonical record.
