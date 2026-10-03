# Evidence

- Imported repository name and docs entry points from README.md.
- Imported SECURITY.md, but no explicit contact channel was parsed, so security_contact = "unknown" is intentional.
- Inferred repo.build from pyproject.toml as `python -m build`.
- Inferred repo.test from .github/workflows/ci.yml as `uv run --no-sync python -X utf8 -m coverage run -m pytest -q test`.
- Imported repo.toolchain.min from pyproject.toml as `3.11` (Python).
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Fresh verification

Prior verified authority was not inherited: this refresh must qualify using its current field scores.

## Documentation correction (2026-09-21T04:36:55.205964Z)

- Withheld docs.root; rejected `https://code.claude.com/docs` because Claude Code integration link is not MoneyPrinterTurbo documentation. Source: [README.md:190](https://github.com/harry0703/MoneyPrinterTurbo/blob/a76b61da5969bfc2bb8d9e169aa8609d9258273f/README.md#L190). No replacement was established by this correction.
- This documentation-only correction advances the record timestamp. Older assessments for other fields retain their original check times and are invalidated by public export until fresh verification; their values were not refreshed.
- This is an overlay record, not a maintainer-controlled canonical record.
