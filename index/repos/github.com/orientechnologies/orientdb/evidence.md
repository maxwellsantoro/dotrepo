# Evidence

- Imported repository name and description from README.md.
- Inferred repo.build from .github/workflows/tests.yml as `mvn -B package --file pom.xml`.
- Inferred repo.test from .github/workflows/tests.yml as `mvn -B clean deploy -P all -DskipTests --file pom.xml`.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
