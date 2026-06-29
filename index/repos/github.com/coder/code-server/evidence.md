# Evidence

- Imported maintainer candidates from CODEOWNERS. Maintainer information was imported from CODEOWNERS; `owners.team` is `@coder/code-server` because it is the clearest imported team signal, but `owners.maintainers` still preserves narrower owner candidates.
- Inferred fallback values for `repo.name` and `repo.description` because the imported files did not provide enough structured metadata.
- Imported repo.build from package.json as `npm run build`.
- Imported repo.test from package.json as `npm test`.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Filled repo.description from GitHub repository metadata when the README surface did not provide one.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
