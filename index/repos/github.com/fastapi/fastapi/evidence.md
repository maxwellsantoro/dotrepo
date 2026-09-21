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

- Corrected evidence for docs.root as `https://fastapi.tiangolo.com`: Pydantic dependency link is not FastAPI documentation. Source: [README.md:24](https://github.com/fastapi/fastapi/blob/50113da16fec53b66b80d75e80a89296de4fa5a5/README.md#L24).
- Withheld docs.getting_started; rejected `https://docs.astral.sh/uv/getting-started/installation/` because uv package-manager installation is not FastAPI installation documentation. Source: [README.md:131](https://github.com/fastapi/fastapi/blob/50113da16fec53b66b80d75e80a89296de4fa5a5/README.md#L131). No replacement was established by this correction.
- This documentation-only correction advances the record timestamp. Older assessments for other fields retain their original check times and are invalidated by public export until fresh verification; their values were not refreshed.
- This is an overlay record, not a maintainer-controlled canonical record.
