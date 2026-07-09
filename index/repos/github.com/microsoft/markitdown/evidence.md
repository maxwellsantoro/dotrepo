# Evidence

- Imported repository name from README.md.
- Imported the security reporting channel from SECURITY.md.
- Inferred repo.build from packages/markitdown-mcp/pyproject.toml as `python -m build`.
- Inferred repo.test from packages/markitdown-mcp/pyproject.toml as `python -m pytest`.
- Imported repo.toolchain.min from packages/markitdown-mcp/pyproject.toml as `3.10` (Python).
- Discovered related relation to github.com/deanmalmgren/textract from README cross-link.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Downgrade guard

A prior verified status was preserved because no previously present field regressed in this refresh.
