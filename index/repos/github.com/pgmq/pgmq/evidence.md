# Evidence

- Imported maintainer candidates from CODEOWNERS.
- Inferred fallback values for `repo.name` and `repo.description` because the imported files did not provide enough structured metadata.
- Left `repo.test` unset because `.github/workflows/client-tests.yml`, `.github/workflows/crate_ci.yml`, and `.github/workflows/extension_upgrade.yml` suggested conflicting test commands.
- Imported repo.toolchain.min from pyproject.toml as `3.10` (Python).
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.test` to `uv run pytest test.py -v` from `.github/workflows/client-tests.yml` after model escalation.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Auto-promotion

Record auto-promoted to verified: all fields are honestly resolved by deterministic promotion scoring.
