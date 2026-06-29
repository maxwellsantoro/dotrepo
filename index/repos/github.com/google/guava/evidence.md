# Evidence

- Imported repository name and docs entry points from README.md.
- Inferred fallback values for `repo.description` because the imported files did not provide enough structured metadata.
- Inferred repo.build from .github/workflows/ci.yml as `./mvnw -B -ntp -Dtoolchain.skip install -U -DskipTests=true -f $ROOT_POM`.
- Inferred repo.test from .github/workflows/ci.yml as `./mvnw -B -ntp -Dtoolchain.skip install -U -DskipTests=true -f $ROOT_POM`.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Filled repo.description from GitHub repository metadata when the README surface did not provide one.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Auto-promotion

Record auto-promoted to verified: all fields are honestly resolved by deterministic promotion scoring.
