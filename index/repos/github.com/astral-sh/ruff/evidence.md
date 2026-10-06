# Evidence

- Imported repository name and docs entry points from README.md.
- Imported maintainer candidates from CODEOWNERS. Maintainer information was imported from broad CODEOWNERS patterns with multiple team owners, so `owners.team` was left unset and `owners.maintainers` preserves the competing owner candidates.
- Imported repo.build from playground/ruff/package.json as `npm run build`.
- Imported repo.test from CONTRIBUTING.md as `cargo test`.
- Imported repo.toolchain.min from Cargo.toml as `1.96` (Rust).
- Discovered related relation to github.com/astral-sh/ruff from README cross-link.
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

2026-10-03 semantic audit withheld repo.build pending command context or usable upstream instructions; prior auto-promotion is superseded. Source inspection timestamps are unchanged.

- Withheld `repo.build` previously extracted from `playground/ruff/package.json` as `npm run build`. Component command lacks repository-default scope and working directory.

## 2026-10-06 bounded risk audit

Statically inspected source revision `9e5ac057c9ea01e0358e79bace5249199352e528` at `2026-10-06T04:07:21.224082Z`. Sources, hashes and all declared field dispositions are retained in [the audit receipt](../../../../telemetry/roadmap-risk-audit-2026-10-06.json).

- `repo.build`: correct-abstention. Withheld playground component build does not establish a root default; the release-build example occurs in benchmarking, not a general build instruction.
- `repo.test`: supported. Guide explicitly describes cargo test and its nextest alternative for Rust tests. Root command retains the runner; this does not claim Python utility or release validation coverage.
- `docs.root`: supported. README explicitly labels https://docs.astral.sh/ruff/ as Docs and documentation.

Record age/status and unrelated facts/assessments remain unchanged. New source-grounded command/context assessments are newer than the record timestamp; the public exporter drops them until a coherent full-record recrawl. No upstream commands were executed, and no fresh pipeline verification or current-HEAD inspection is claimed. Absence is limited to the inspected sources.

This is an overlay record, not a maintainer-controlled canonical record.
