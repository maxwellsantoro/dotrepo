# Evidence

- Inferred fallback values for `repo.name` and `repo.description` because the imported files did not provide enough structured metadata.
- Imported repo.build from pom.xml as `./mvnw package`.
- Imported repo.test from pom.xml as `./mvnw test`.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Filled repo.description from GitHub repository metadata when the README surface did not provide one.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Downgrade guard

A prior verified status was preserved because no previously present field regressed in this refresh.
