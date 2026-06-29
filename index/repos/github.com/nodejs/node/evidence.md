# Evidence

- Imported repository name and description from README.md.
- Imported maintainer candidates from CODEOWNERS. Maintainer information was imported from broad CODEOWNERS patterns with multiple team owners, so `owners.team` was left unset and `owners.maintainers` preserves the competing owner candidates.
- Imported the security reporting channel from SECURITY.md.
- Inferred repo.build from .github/workflows/build-tarball.yml as `make -C "$TAR_DIR" build-ci -j4 V=1`.
- Left `repo.test` unset because `.github/workflows/build-shared.yml` and `.github/workflows/build-tarball.yml` suggested conflicting test commands.
- This is an overlay record, not a maintainer-controlled canonical record.

- Left `repo.test` unset after deterministic escalation: no unique build/test candidate after deterministic tier walk.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
