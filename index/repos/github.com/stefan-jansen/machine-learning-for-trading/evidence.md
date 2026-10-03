# Evidence

- Imported repository name and docs entry points from README.md.
- Inferred repo.build from pyproject.toml as `python -m build`.
- Inferred repo.test from .github/workflows/test.yml as `uv pip install --constraint /tmp/locked-constraints.txt jupytext pytest nbformat`.
- Imported repo.toolchain.min from pyproject.toml as `3.14` (Python).
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

- Withheld docs.root; rejected `https://jupytext.readthedocs.io/` because Jupytext tooling reference is not documentation for this book repository. Source: [README.md:333](https://github.com/stefan-jansen/machine-learning-for-trading/blob/567b1040016ca3a91dbaa80dede040dc045b1ea0/README.md#L333). No replacement was established by this correction.
- This documentation-only correction advances the record timestamp. Older assessments for other fields retain their original check times and are invalidated by public export until fresh verification; their values were not refreshed.
- This is an overlay record, not a maintainer-controlled canonical record.
