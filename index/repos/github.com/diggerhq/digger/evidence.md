# Evidence

- Imported repository docs entry points from README.md.
- Inferred fallback values for `repo.name` because the imported files did not provide enough structured metadata.
- Imported repo.build from docs/package.json as `npm run build`.
- Inferred repo.test from .github/workflows/backend_test.yml as `go test ./...`.
- Imported repo.toolchain.min from go.mod as `1.25.0` (Go).
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Fresh verification

Prior verified authority was not inherited: this refresh must qualify using its current field scores.

## Command semantic correction (2026-10-03)

2026-10-03 semantic audit withheld repo.build pending command context or usable upstream instructions; repository-default applicability remains unresolved. Source inspection timestamps are unchanged.

- Withheld `repo.build` previously extracted from `docs/package.json` as `npm run build`. Component command lacks repository-default scope and working directory.
