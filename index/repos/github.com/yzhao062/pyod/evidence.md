# Evidence

- Imported SECURITY.md, but no explicit contact channel was parsed, so security_contact = "unknown" is intentional.
- Inferred fallback values for `repo.name` and `repo.description` because the imported files did not provide enough structured metadata.
- Inferred repo.build from .github/workflows/testing.yml as `python -m build`.
- Inferred repo.test from .github/workflows/testing-cron.yml as `pip install pytest`.
- Imported repo.toolchain.min from pyproject.toml as `3.9` (Python).
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Fresh verification

Prior verified authority was not inherited: this refresh must qualify using its current field scores.
