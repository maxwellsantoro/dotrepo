# Evidence

- Inferred fallback values for `repo.name` because the imported files did not provide enough structured metadata.
- Left `repo.build` unset because `.github/workflows/build.yml` suggested an unsafe shell-like command.
- Left `repo.test` unset because `.github/workflows/build.yml` suggested an unsafe shell-like command.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Auto-promotion

All fields are high-confidence present or high-confidence absent. Record auto-promoted to verified status.
