# Evidence

- Imported repository docs entry points from README.md.
- Imported maintainer candidates from CODEOWNERS.
- Inferred fallback values for `repo.name` because the imported files did not provide enough structured metadata.
- Imported repo.build from Makefile as `make all`.
- Imported repo.test from Makefile as `make test`.
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

- repo.build: `make all` -> withheld (inspected `Makefile`)

Receipt and source hashes: [command-source audit](../../../../telemetry/command-semantics-20261004/report.json).

## 2026-10-06 bounded risk audit

Statically inspected source revision `892243986918fa188e8a52bf73d40a5383581d5c` at `2026-10-06T04:07:21.224082Z`. Sources, hashes and all declared field dispositions are retained in [the audit receipt](../../../../telemetry/roadmap-risk-audit-2026-10-06.json).

- `repo.build`: correct-abstention. make all was an assignment false positive, already removed. DEVELOPERS.md declares make binaries for cloud providers, not a default build of every surface.
- `repo.test`: supported. Literal root test target iterates core and cloud providers; wrapper preserves child Make prerequisites. DEVELOPERS.md explicitly documents make test.
- `docs.root`: supported. README explicitly states full Nitric documentation is at nitric.io/docs.

Record age/status and unrelated facts/assessments remain unchanged. New source-grounded command/context assessments are newer than the record timestamp; the public exporter drops them until a coherent full-record recrawl. No upstream commands were executed, and no fresh pipeline verification or current-HEAD inspection is claimed. Absence is limited to the inspected sources.

This is an overlay record, not a maintainer-controlled canonical record.
