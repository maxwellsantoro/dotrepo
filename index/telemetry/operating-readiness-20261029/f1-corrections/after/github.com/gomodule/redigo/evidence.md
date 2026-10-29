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

## October 29 source-bound correction

The import observations above are historical. This bounded audit inspected only the fields below; other values, field assessments, record generation time, GitHub metadata and existing trust metadata were preserved. No upstream command was executed.

- `docs.root`: retained exact declaration `https://pkg.go.dev/github.com/gomodule/redigo/redis`. README explicitly labels the existing pkg.go.dev value API Reference and uses the same path for its GoDoc badge and features. Exact source-declared URL retained; bounded live target status/redirect/content observations are retained separately in index/telemetry/operating-readiness-20261029/f1-corrections. Target content is mutable and does not establish source-version parity.
  - Source: https://github.com/gomodule/redigo/blob/57c8b99ccb90c3401bec6e09289081e8b78b3bde/README.markdown lines 18–23; SHA-256 `9fade03f42daf7476a14204e80bb2dd64593bf81f4bedf332d00625a3b6f522d`.
- `repo.build`: withheld scalar. README declares go get installation, not a repository-default go build ./... step. Release workflow uses GoReleaser. The original command may build the library but its claimed default is not source-established. Withheld repository-default scalar; narrower/prepared execution may remain valid. No upstream execution observed.
  - Source: https://github.com/gomodule/redigo/blob/57c8b99ccb90c3401bec6e09289081e8b78b3bde/README.markdown lines 25–32; SHA-256 `9fade03f42daf7476a14204e80bb2dd64593bf81f4bedf332d00625a3b6f522d`.
  - Source: https://github.com/gomodule/redigo/blob/57c8b99ccb90c3401bec6e09289081e8b78b3bde/.github/workflows/release-build.yml lines 20–32; SHA-256 `1e4c7c2dae8bc6b2286ee87e5055900ef4d08c53608d95213bb4d8b484dd06b8`.
- `repo.test`: withheld scalar. CI installs Redis before go test -race ./.... Test helper executes redis-server --version and starts the binary. The bare old scalar can run the same packages with setup, but drops Redis prerequisites and the source-owned race flag. Withheld repository-default scalar; narrower/prepared execution may remain valid. No upstream execution observed.
  - Source: https://github.com/gomodule/redigo/blob/57c8b99ccb90c3401bec6e09289081e8b78b3bde/.github/workflows/go-test.yml lines 11–38; SHA-256 `f6e5dca75defdea9f22c29c189a2ca46b398bc19018be5f41e43055e329fa84d`.
  - Source: https://github.com/gomodule/redigo/blob/57c8b99ccb90c3401bec6e09289081e8b78b3bde/redis/test_test.go lines 40–65; SHA-256 `91e3066bd8b8eb32a5b778c6cbff27e08cd31b690d0a8424368cbd49e96cf17b`.
  - Source: https://github.com/gomodule/redigo/blob/57c8b99ccb90c3401bec6e09289081e8b78b3bde/redis/test_test.go lines 95–123; SHA-256 `91e3066bd8b8eb32a5b778c6cbff27e08cd31b690d0a8424368cbd49e96cf17b`.

Frozen source-only assessment: `index/telemetry/operating-readiness-20261029/f1-source-assessments.json`; source freeze SHA-256 `779bf4cea196f16ff3f16526e71321367f351fe0a2f5eaeea166099fe8b10d98`. New field checks use their own time; this does not refresh the whole record.
