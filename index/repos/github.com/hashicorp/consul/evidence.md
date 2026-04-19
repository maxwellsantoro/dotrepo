# Evidence

- Imported repository description from README.md.
- Imported maintainer candidates from CODEOWNERS. Maintainer information was imported from broad CODEOWNERS patterns with multiple team owners, so `owners.team` was left unset and `owners.maintainers` preserves the competing owner candidates.
- Inferred fallback values for `repo.name` because the imported files did not provide enough structured metadata.
- Imported repo.build from go.mod as `go build ./...`.
- Imported repo.test from go.mod as `go test ./...`.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Filled repo.description from GitHub repository metadata when the README surface did not provide one.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
