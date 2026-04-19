# Evidence

- Imported repository description from README.md.
- Inferred fallback values for `repo.name` because the imported files did not provide enough structured metadata.
- Left `repo.build` unset because `Cargo.toml` and `.github/workflows/ci.yaml` suggested conflicting build commands.
- Left `repo.test` unset because `Cargo.toml` and `.github/workflows/ci.yaml` suggested conflicting test commands.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
