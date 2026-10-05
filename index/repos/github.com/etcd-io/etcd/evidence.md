# Evidence

- Imported repository name from README.md.
- Imported the security reporting channel from SECURITY.md. SECURITY.md provided a policy or reporting URL rather than a direct mailbox, so `security_contact` preserves that URL.
- Imported repo.build from Makefile as `make build`.
- Imported repo.test from CONTRIBUTING.md as `go test -v -c -count 1`.
- Imported repo.toolchain.min from go.mod as `1.27` (Go).
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Auto-promotion

All fields are high-confidence present or high-confidence absent. Record auto-promoted to verified status.

## 2026-10-04 command semantics correction

The preceding import and auto-promotion entries are historical and superseded for the fields below. Pinned sources were inspected statically; upstream task recipes were not executed. This does not establish task correctness or refresh other facts. Prior affected field assessments were removed, and verified authority was superseded where necessary.

- repo.test: `go test -v -c -count 1` -> `make test-unit` (inspected `CONTRIBUTING.md`)

Receipt and source hashes: [command-source audit](../../../../telemetry/command-semantics-20261004/report.json).
