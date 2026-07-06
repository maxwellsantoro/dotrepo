# Evidence

- Imported repository name from README.md.
- Inferred repo.build from build.gradle.kts as `./gradlew build`.
- Inferred repo.test from build.gradle.kts as `./gradlew test`.
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.name` to `HyperCeiler` from `GitHub API` after deterministic escalation.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Downgrade guard

A prior verified status was preserved because no previously present field regressed in this refresh.
