# Evidence

- Imported repository name and docs entry points from README.md.
- Imported the security reporting channel from SECURITY.md. SECURITY.md provided a policy or reporting URL rather than a direct mailbox, so `security_contact` preserves that URL.
- Imported repo.build from examples/basic-crud-application/server/package.json as `npm run build`.
- Imported repo.test from examples/basic-crud-application/server/package.json as `npm test`.
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

## Command semantic correction (2026-10-03)

2026-10-03 semantic audit withheld repo.build, repo.test pending command context or usable upstream instructions; prior auto-promotion is superseded. Source inspection timestamps are unchanged.

- Withheld `repo.build` previously extracted from `examples/basic-crud-application/server/package.json` as `npm run build`. Component command lacks repository-default scope and working directory.
- Withheld `repo.test` previously extracted from `examples/basic-crud-application/server/package.json` as `npm test`. Component command lacks repository-default scope and working directory.

## 2026-10-06 bounded risk audit

Statically inspected source revision `b5da079228666fcabd97166486d5f6a110826bc8` at `2026-10-06T04:07:21.224082Z`. Sources, hashes and all declared field dispositions are retained in [the audit receipt](../../../../telemetry/roadmap-risk-audit-2026-10-06.json).

- `repo.build`: missing-supported-candidate. Guide explicitly declares TypeScript compilation for all workspaces. This is a compilation candidate, not a promoted example-package scalar default.
- `repo.test`: missing-supported-candidate. Guide explicitly declares tests for all workspaces; keep the npm wrapper to preserve each workspace script. The inspected socket.io workspace script includes formatting, compilation and test substeps.
- `docs.root`: supported. README explicitly links the Socket.IO v4 documentation at this URL.

Record age/status and unrelated facts/assessments remain unchanged. New source-grounded command/context assessments are newer than the record timestamp; the public exporter drops them until a coherent full-record recrawl. No upstream commands were executed, and no fresh pipeline verification or current-HEAD inspection is claimed. Absence is limited to the inspected sources.

This is an overlay record, not a maintainer-controlled canonical record.
