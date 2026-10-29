# Evidence

- Imported repository name from README.md.
- Inferred repo.build from go.mod as `go build ./...`.
- Inferred repo.test from go.mod as `go test ./...`.
- Imported repo.toolchain.min from go.mod as `1.20` (Go).
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## October 29 source-bound correction

The import observations above are historical. This bounded audit inspected only the fields below; other values, field assessments, record generation time, GitHub metadata and existing trust metadata were preserved. No upstream command was executed.

- `docs.root`: retained exact declaration `https://pkg.go.dev/github.com/IBM/fp-go`. README explicitly labels pkg.go.dev root-module page API Documentation, with separate V2 documentation. Retain the declared entrypoint without implying v1 command coverage of every module. Exact source-declared URL retained; bounded live target status/redirect/content observations are retained separately in index/telemetry/operating-readiness-20261029/f1-corrections. Target content is mutable and does not establish source-version parity.
  - Source: https://github.com/IBM/fp-go/blob/42e25c64425e2291bd5b281aa852b7a790526204/README.md lines 56–60; SHA-256 `f92d9a6e245607599eedee3a941ffcaf0aadef007d3cbbf6b26a04ee653a433a`.
- `repo.build`: withheld scalar. go build ./... may build root v1, but retained docs/workflows do not declare it as repository-default build. CI separately handles v1/v2/gen-v2; conventional syntax does not establish an aggregate source-owned default. Withheld repository-default scalar; narrower/prepared execution may remain valid. No upstream execution observed.
  - Source: https://github.com/IBM/fp-go/blob/42e25c64425e2291bd5b281aa852b7a790526204/go.mod lines 1–5; SHA-256 `d99a7fedebc0034b3ee99bb1e820f0e93660d2e44e6e3b7a5de8252afab23544`.
  - Source: https://github.com/IBM/fp-go/blob/42e25c64425e2291bd5b281aa852b7a790526204/v2/go.mod lines 1–5; SHA-256 `592f7929f786535e9ce99626ba3caef64d209a32d103886819b6006da7c4e254`.
  - Source: https://github.com/IBM/fp-go/blob/42e25c64425e2291bd5b281aa852b7a790526204/gen/v2/go.mod lines 1–5; SHA-256 `f570b0499adf862d968f0ecac7a550da39ca66438e6a4fe71352fc44525409d6`.
  - Source: https://github.com/IBM/fp-go/blob/42e25c64425e2291bd5b281aa852b7a790526204/.github/workflows/build.yml lines 133–151; SHA-256 `1931d37e0f552e7451472cbc4e75f119a09fc6d8d70819aa29e0481173e4a25c`.
- `repo.test`: withheld scalar. Root go test ./... covers root v1 but omits separate v2 and gen/v2 modules. CI requires distinct module jobs, Go matrices, go mod tidy preparation and race/coverage invocations. Withheld repository-default scalar; narrower/prepared execution may remain valid. No upstream execution observed.
  - Source: https://github.com/IBM/fp-go/blob/42e25c64425e2291bd5b281aa852b7a790526204/.github/workflows/build.yml lines 21–44; SHA-256 `1931d37e0f552e7451472cbc4e75f119a09fc6d8d70819aa29e0481173e4a25c`.
  - Source: https://github.com/IBM/fp-go/blob/42e25c64425e2291bd5b281aa852b7a790526204/.github/workflows/build.yml lines 65–86; SHA-256 `1931d37e0f552e7451472cbc4e75f119a09fc6d8d70819aa29e0481173e4a25c`.
  - Source: https://github.com/IBM/fp-go/blob/42e25c64425e2291bd5b281aa852b7a790526204/.github/workflows/build.yml lines 107–128; SHA-256 `1931d37e0f552e7451472cbc4e75f119a09fc6d8d70819aa29e0481173e4a25c`.
  - Source: https://github.com/IBM/fp-go/blob/42e25c64425e2291bd5b281aa852b7a790526204/v2/go.mod lines 1–5; SHA-256 `592f7929f786535e9ce99626ba3caef64d209a32d103886819b6006da7c4e254`.
  - Source: https://github.com/IBM/fp-go/blob/42e25c64425e2291bd5b281aa852b7a790526204/gen/v2/go.mod lines 1–5; SHA-256 `f570b0499adf862d968f0ecac7a550da39ca66438e6a4fe71352fc44525409d6`.

Frozen source-only assessment: `index/telemetry/operating-readiness-20261029/f1-source-assessments.json`; source freeze SHA-256 `779bf4cea196f16ff3f16526e71321367f351fe0a2f5eaeea166099fe8b10d98`. New field checks use their own time; this does not refresh the whole record.
