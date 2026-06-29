# Evidence

- Imported repository name, description, and docs entry points from README.md.
- Imported maintainer candidates from CODEOWNERS. Maintainer information was imported from CODEOWNERS; `owners.team` is `@github/js` because it is the clearest imported team signal, but `owners.maintainers` still preserves narrower owner candidates.
- Inferred repo.build from .github/workflows/mc-release.yml as `./gradlew assemble`.
- Inferred repo.test from .github/workflows/mc-release.yml as `./gradlew assemble`.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
