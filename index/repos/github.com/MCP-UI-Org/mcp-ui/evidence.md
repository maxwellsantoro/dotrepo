# Evidence

- Imported repository name from README.md.
- Imported SECURITY.md, but no explicit contact channel was parsed, so security_contact = "unknown" is intentional.
- Ignored component-scoped commands from `examples/python-server-demo/pyproject.toml` as repository defaults.
- Imported repo.build from package.json as `pnpm build`.
- Imported repo.test from package.json as `pnpm test`.
- Imported repo.toolchain.min from examples/python-server-demo/pyproject.toml as `3.10` (Python).
- Conflicting documentation declarations in README.md; abstained from docs.getting_started.
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.name` to `mcp-ui` from `GitHub API` after deterministic escalation.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Fresh verification

Prior verified authority was not inherited: this refresh must qualify using its current field scores.
