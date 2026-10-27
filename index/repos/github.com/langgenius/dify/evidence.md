# Evidence

- Imported repository name and docs entry points from README.md.
- Imported maintainer candidates from CODEOWNERS.
- Imported the security reporting channel from SECURITY.md. SECURITY.md provided a policy or reporting URL rather than a direct mailbox, so `security_contact` preserves that URL.
- Ignored component-scoped commands from `web/package.json` as repository defaults.
- Ignored component-scoped commands from `dify-agent/pyproject.toml` as repository defaults.
- Imported repo.test from Makefile as `make test`.
- Imported repo.toolchain.min from dify-agent/pyproject.toml as `3.13` (Python).
- Imported docs.root as `https://docs.dify.ai`. Explicit documentation link at README.md:6: <a href="https://docs.dify.ai">Documentation</a> ·
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.name` to `dify` from `GitHub API` after deterministic escalation.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Auto-promotion

All fields are high-confidence present or high-confidence absent. Record auto-promoted to verified status.
