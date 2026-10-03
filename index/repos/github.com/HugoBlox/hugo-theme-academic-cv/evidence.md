# Evidence

- Imported repository docs entry points from README.md.
- Inferred fallback values for `repo.name` because the imported files did not provide enough structured metadata.
- Imported repo.build from package.json as `pnpm build`.
- Inferred repo.test from go.mod as `go test ./...`.
- Imported repo.toolchain.min from go.mod as `1.19` (Go).
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
