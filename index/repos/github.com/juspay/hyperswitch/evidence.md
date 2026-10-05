# Evidence

- Imported repository name from README.md.
- Imported maintainer candidates from CODEOWNERS. Maintainer information was imported from broad CODEOWNERS patterns; `owners.team` prefers `@juspay/hyperswitch-maintainers` from the repo-wide rule, and `owners.maintainers` preserves narrower owner candidates.
- Imported repo.build from cypress-tests/package.json as `npm run build`.
- Imported repo.test from Makefile as `cargo test --all-features`.
- Imported repo.toolchain.min from Cargo.toml as `1.85.0` (Rust).
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.name` to `hyperswitch` from `GitHub API` after deterministic escalation.
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

- Withheld `repo.build` previously extracted from `cypress-tests/package.json` as `npm run build`. Component command lacks repository-default scope and working directory.

## 2026-10-04 command semantics correction

The preceding import and auto-promotion entries are historical and superseded for the fields below. Pinned sources were inspected statically; upstream task recipes were not executed. This does not establish task correctness or refresh other facts. Prior affected field assessments were removed, and verified authority was superseded where necessary.

- repo.test: `cargo test --all-features` -> `make test` (inspected `Makefile`)

Receipt and source hashes: [command-source audit](../../../../telemetry/command-semantics-20261004/report.json).
