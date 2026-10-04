# Evidence

- Imported repository metadata from README.md.
- Inferred fallback values for `repo.name` and `repo.description` because the imported files did not provide enough structured metadata.
- Imported repo.build from editors/code/package.json as `npm run build`.
- Imported repo.test from editors/code/package.json as `npm test`.
- Imported repo.toolchain.min from Cargo.toml as `1.98` (Rust).
- This is an overlay record, not a maintainer-controlled canonical record.

- Deepened `owners.security_contact` from `README.md` during deterministic escalation.
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

- Withheld `repo.build` previously extracted from `editors/code/package.json` as `npm run build`. Component command lacks repository-default scope and working directory.
- Withheld `repo.test` previously extracted from `editors/code/package.json` as `npm test`. Component command lacks repository-default scope and working directory.
