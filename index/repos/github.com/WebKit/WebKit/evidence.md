# Evidence

- Imported maintainer candidates from CODEOWNERS. Maintainer information was imported from broad CODEOWNERS patterns with multiple team owners, so `owners.team` was left unset and `owners.maintainers` preserves the competing owner candidates.
- Inferred fallback values for `repo.name` and `repo.description` because the imported files did not provide enough structured metadata.
- Imported repo.build from Makefile as `make all`.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## 2026-10-04 command semantics correction

The preceding import and auto-promotion entries are historical and superseded for the fields below. Pinned sources were inspected statically; upstream task recipes were not executed. This does not establish task correctness or refresh other facts. Prior affected field assessments were removed, and verified authority was superseded where necessary.

- repo.build: `make all` -> withheld (inspected `Makefile`)

Receipt and source hashes: [command-source audit](../../../../telemetry/command-semantics-20261004/report.json).
