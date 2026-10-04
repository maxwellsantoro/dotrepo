# Evidence

- Imported repository name from README.md.
- Imported the security reporting channel from SECURITY.md.
- Inferred repo.build from packages/markitdown-mcp/pyproject.toml as `python -m build`.
- Inferred repo.test from .github/workflows/tests.yml as `pip install ./packages/markitdown ./packages/markitdown-ocr pytest`.
- Imported repo.toolchain.min from packages/markitdown-mcp/pyproject.toml as `3.10` (Python).
- Discovered related relation to github.com/deanmalmgren/textract from README cross-link.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Fresh verification

Prior verified authority was not inherited: this refresh must qualify using its current field scores.

## Command semantic correction (2026-10-03)

2026-10-03 semantic audit withheld repo.build pending command context or usable upstream instructions; repository-default applicability remains unresolved. Source inspection timestamps are unchanged.

- Withheld `repo.build` previously extracted from `packages/markitdown-mcp/pyproject.toml` as `python -m build`. Component command lacks repository-default scope and working directory.
