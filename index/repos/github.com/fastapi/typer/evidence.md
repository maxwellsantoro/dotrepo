# Evidence

- Imported repository name and docs entry points from README.md.
- Inferred repo.build from pyproject.toml as `python -m build`.
- Inferred repo.test from pyproject.toml as `python -m pytest`.
- Imported repo.toolchain.min from pyproject.toml as `3.10` (Python).
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

## Documentation correction (2026-09-21T04:36:55.205964Z)

- Corrected evidence for docs.root as `https://typer.tiangolo.com`: Rich dependency link is not Typer documentation. Source: [README.md:21](https://github.com/fastapi/typer/blob/a80f6e5ecd74f32b983cca336a2f3cba98d9853a/README.md#L21).
- Withheld docs.getting_started; rejected `https://docs.astral.sh/uv/getting-started/installation/` because uv package-manager installation is not Typer installation documentation. Source: [README.md:46](https://github.com/fastapi/typer/blob/a80f6e5ecd74f32b983cca336a2f3cba98d9853a/README.md#L46). No replacement was established by this correction.
- This documentation-only correction advances the record timestamp. Older assessments for other fields retain their original check times and are invalidated by public export until fresh verification; their values were not refreshed.
- This is an overlay record, not a maintainer-controlled canonical record.
