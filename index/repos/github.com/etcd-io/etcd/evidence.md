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

## 2026-10-06 bounded command-source checkpoint

Statically inspected pinned revision `f094b9834a5aa0ef748b91509b824e324dd65700` at `2026-10-06T04:00:48.158597Z`. Sources and hashes are retained in [the checkpoint receipt](../../../../telemetry/roadmap-factual-checkpoint-2026-10-06.json). No upstream command was executed.

- `repo.build = "make build"` is retained exactly. The literal root Make target invokes `scripts/build.sh`; the contribution guide recommends this entrypoint after development setup.
- `repo.test = "make test-unit"` is retained exactly as the documented unit-test entrypoint. The root Make target selects the unit pass, which traverses workspace modules. It is not a claim to run integration or end-to-end tests.
- Both scalar contexts retain the repository root, repository scope and the guide's supported `linux-amd64` development setup with Go and listed build tools. Script checks require the root module. Prerequisites are descriptions, not automatically executable setup or a claim that the environment was prepared.
- The historical `go test -v -c -count 1` is the package-specific compilation step preceding a stress invocation, not a repository test runner. The October 4 correction is confirmed without rewriting its receipt.

Record `generated_at`, status and unrelated field assessments are unchanged. The new command/context assessments are newer than that factual record timestamp and do not rejuvenate the whole record; the current public exporter/reference consumer consequently withholds them until a full-record crawl produces coherent evidence. This checkpoint does not establish current upstream HEAD or runtime correctness.

This is an overlay record, not a maintainer-controlled canonical record.
