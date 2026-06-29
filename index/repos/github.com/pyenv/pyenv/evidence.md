# Evidence

- Imported repository name from README.md.
- Imported maintainer candidates from CODEOWNERS.
- Inferred fallback values for `repo.description` because the imported files did not provide enough structured metadata.
- Left `repo.build` unset because `.github/workflows/modified_scripts_build.yml` and `.github/workflows/ubuntu_build.yml` suggested conflicting build commands.
- Inferred repo.test from .github/workflows/pyenv_tests.yml as `make test`.
- Discovered related relation to github.com/rbenv/rbenv from README cross-link.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Filled repo.description from GitHub repository metadata when the README surface did not provide one.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
