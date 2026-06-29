# Evidence

- Imported repository name and description from README.md.
- Imported the security reporting channel from SECURITY.md.
- Inferred repo.build from .github/workflows/build.yml as `./gradlew --build-cache --info $SCAN_ARG check releaseTarGz -x test`.
- Inferred repo.test from .github/workflows/build.yml as `./gradlew --build-cache --info $SCAN_ARG check releaseTarGz -x test`.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Auto-promotion

Record auto-promoted to verified: all fields are honestly resolved by deterministic promotion scoring.
