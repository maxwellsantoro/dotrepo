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
