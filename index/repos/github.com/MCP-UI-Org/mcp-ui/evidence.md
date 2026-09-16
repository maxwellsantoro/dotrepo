# Evidence

- Imported repository name from README.md.
- Imported SECURITY.md, but no explicit contact channel was parsed, so security_contact = "unknown" is intentional.
- Imported repo.build from package.json as `pnpm build`.
- Imported repo.test from package.json as `pnpm test`.
- Imported repo.toolchain.min from examples/python-server-demo/pyproject.toml as `3.10` (Python).
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.name` to `mcp-ui` from `GitHub API` after deterministic escalation.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Auto-promotion

All fields are high-confidence present or high-confidence absent. Record auto-promoted to verified status.
