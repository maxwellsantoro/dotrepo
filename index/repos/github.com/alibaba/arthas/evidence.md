# Evidence

- Imported repository name, description, and docs entry points from README.md.
- Inferred repo.build from .github/workflows/release.yaml as `mvn -V -ntp clean package -P full`.
- Inferred repo.test from .github/workflows/publish-maven-central.yml as `mvn -B -ntp -DskipTests`.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Auto-promotion

Record auto-promoted to verified: all fields are honestly resolved by deterministic promotion scoring.
