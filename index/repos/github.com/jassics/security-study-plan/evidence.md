# Evidence

- Inferred fallback values for `repo.name` because the imported files did not provide enough structured metadata.
- Discovered related relation to github.com/jwasham/coding-interview-university from README cross-link.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Auto-promotion

All fields are high-confidence present or high-confidence absent. Record auto-promoted to verified status.

## 2026-10-06 bounded risk audit

Statically inspected source revision `5eab1faf7e919007c7e793948a242d45a332ed4e` at `2026-10-06T04:07:21.224082Z`. Sources, hashes and all declared field dispositions are retained in [the audit receipt](../../../../telemetry/roadmap-risk-audit-2026-10-06.json).

- `repo.build`: correct-abstention. Inspected source is a prose study-plan collection, with no declared build entrypoint.
- `repo.test`: correct-abstention. Inspected source is a prose study-plan collection, with no declared executable test suite.
- `docs.root`: unsupported-documentation-association. README neither references cybercloud.guru nor declares that external site as this study-plan documentation. No outside-site reachability claim was used as ownership evidence.

Record age/status and unrelated facts/assessments remain unchanged. New source-grounded command/context assessments are newer than the record timestamp; the public exporter drops them until a coherent full-record recrawl. No upstream commands were executed, and no fresh pipeline verification or current-HEAD inspection is claimed. Absence is limited to the inspected sources.

This is an overlay record, not a maintainer-controlled canonical record.
