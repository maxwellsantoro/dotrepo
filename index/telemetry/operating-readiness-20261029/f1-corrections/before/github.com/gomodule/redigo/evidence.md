# Evidence

- Imported repository name, description, and docs entry points from README.markdown.
- Inferred repo.build from go.mod as `go build ./...`.
- Inferred repo.test from go.mod as `go test ./...`.
- Imported repo.toolchain.min from go.mod as `1.17` (Go).
- Imported docs.root as `https://pkg.go.dev/github.com/gomodule/redigo/redis`. Explicit documentation link at README.markdown:21: - [API Reference](https://pkg.go.dev/github.com/gomodule/redigo/redis)
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
