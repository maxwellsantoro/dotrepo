# Evidence

- Imported repository name and docs entry points from README.md.
- Imported the security reporting channel from SECURITY.md.
- Inferred fallback values for `repo.description` because the imported files did not provide enough structured metadata.
- Imported repo.build from GNUmakefile as `make build`.
- Imported repo.test from GNUmakefile as `make test`.
- Imported repo.toolchain.min from Cargo.toml as `1.88.0` (Rust).
- Discovered related relation to github.com/uutils/coreutils from Cargo.toml repository.
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

- repo.build: `make build` -> `make all` (inspected `GNUmakefile`)

Receipt and source hashes: [command-source audit](../../../../telemetry/command-semantics-20261004/report.json).
