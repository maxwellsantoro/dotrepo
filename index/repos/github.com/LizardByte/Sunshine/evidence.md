# Evidence

- Imported repository name from README.md.
- Inferred fallback values for `repo.description` because the imported files did not provide enough structured metadata.
- Imported repo.build from package.json as `npm run build`.
- Left `repo.test` unset because `package.json` and `pyproject.toml` suggested conflicting test commands.
- Imported repo.toolchain.min from pyproject.toml as `3.14` (Python).
- Discovered related relation to github.com/LizardByte/Sunshine from package.json repository.
- This is an overlay record, not a maintainer-controlled canonical record.

- Left `repo.test` unset after deterministic escalation: conflicting test candidates from package.json, pyproject.toml. Preserved 2 candidate command(s) in `repo.test_candidates` instead of discarding them.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
