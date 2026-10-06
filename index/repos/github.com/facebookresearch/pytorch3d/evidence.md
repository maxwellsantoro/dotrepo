# Evidence

- Imported repository name and docs entry points from README.md.
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.name` to `pytorch3d` from `GitHub API` after deterministic escalation.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Auto-promotion

All fields are high-confidence present or high-confidence absent. Record auto-promoted to verified status.

## 2026-10-06 bounded risk audit

Statically inspected source revision `978cd99221b9e0a6a568f1d427854d73363265cf` at `2026-10-06T04:07:21.224082Z`. Sources, hashes and all declared field dispositions are retained in [the audit receipt](../../../../telemetry/roadmap-risk-audit-2026-10-06.json).

- `repo.build`: correct-abstention. INSTALL.md documents multiple installation/build environments; no selected complete scalar build procedure is established by this inspection.
- `repo.test`: missing-supported-answer. Linked contribution guide explicitly requires this test suite command from the project root, following INSTALL.md setup. Prior root-only discovery missed the guide.
- `docs.root`: supported. README explicitly links PyTorch3D documentation at this URL.

Record age/status and unrelated facts/assessments remain unchanged. New source-grounded command/context assessments are newer than the record timestamp; the public exporter drops them until a coherent full-record recrawl. No upstream commands were executed, and no fresh pipeline verification or current-HEAD inspection is claimed. Absence is limited to the inspected sources.

This is an overlay record, not a maintainer-controlled canonical record.
