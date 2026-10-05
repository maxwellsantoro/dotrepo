# Evidence

- Imported repository docs entry points from README.md.
- Inferred fallback values for `repo.name` because the imported files did not provide enough structured metadata.
- Ignored component-scoped commands from `docs/package.json` as repository defaults.
- Inferred repo.build from go.mod as `go build ./...`.
- Inferred repo.test from go.mod as `go test ./...`.
- Imported repo.toolchain.min from go.mod as `1.25.0` (Go).
- Imported docs.root as `https://docs.digger.dev/`. Explicit documentation link at README.md:8: <a href="https://docs.digger.dev/">Docs</a>
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
