# Evidence

- Imported repository name from README.md.
- Imported repo.build from package.json as `npm run build`.
- Discovered related relation to github.com/andrewngu/sound-redux from package.json repository.
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

## 2026-10-06 bounded risk audit

Statically inspected source revision `c5f36935c2ab07fbbeeaf63573434fd815f503ad` at `2026-10-06T04:07:21.224082Z`. Sources, hashes and all declared field dispositions are retained in [the audit receipt](../../../../telemetry/roadmap-risk-audit-2026-10-06.json).

- `repo.build`: supported. Root package.json declares build plus prebuild clean/copy hooks; preserve npm run build. README declares npm install preparation.
- `repo.test`: correct-abstention. Root package.json declares build/lint/start scripts but no test script; inspected README supplies no test instruction.
- `docs.root`: wrong-documentation-association. README identifies this URL as the live application demo (See it in action), which it also says is not working; it is not declared documentation.

Record age/status and unrelated facts/assessments remain unchanged. New source-grounded command/context assessments are newer than the record timestamp; the public exporter drops them until a coherent full-record recrawl. No upstream commands were executed, and no fresh pipeline verification or current-HEAD inspection is claimed. Absence is limited to the inspected sources.

This is an overlay record, not a maintainer-controlled canonical record.
