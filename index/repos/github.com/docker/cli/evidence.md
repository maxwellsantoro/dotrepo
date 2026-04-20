# Evidence

- Imported repository name from README.md.
- Imported maintainer candidates from CODEOWNERS. Maintainer information was imported from CODEOWNERS; `owners.team` is `@docker/runtime-owners` because it is the clearest imported team signal, but `owners.maintainers` still preserves narrower owner candidates.
- Imported the security reporting channel from SECURITY.md.
- Inferred fallback values for `repo.description` because the imported files did not provide enough structured metadata.
- Inferred repo.test from .github/workflows/test.yml as `go test -coverprofile=/tmp/coverage.txt $(go list ./... | grep -vE '^github.com/docker/cli/e2e/')`.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Filled repo.description from GitHub repository metadata when the README surface did not provide one.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
