# Evidence

- Imported the security reporting channel from SECURITY.md.
- Inferred fallback values for `repo.name` because the imported files did not provide enough structured metadata.
- Ignored component-scoped commands from `tests/setup.py` as repository defaults.
- Ignored component-scoped commands from `tests/setup.cfg` as repository defaults.
- Inferred repo.build from build.gradle as `./gradlew build`.
- Inferred repo.test from build.gradle as `./gradlew test`.
- Discovered related relation to github.com/apache/kafka from README cross-link.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
