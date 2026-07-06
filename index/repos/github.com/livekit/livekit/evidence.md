# Evidence

- Imported repository docs entry points from README.md.
- Imported maintainer candidates from CODEOWNERS.
- Inferred fallback values for `repo.name` because the imported files did not provide enough structured metadata.
- Inferred repo.build from go.mod as `go build ./...`.
- Left `repo.test` unset because `.github/workflows/buildtest.yaml` suggested an unsafe shell-like command.
- Imported repo.toolchain.min from go.mod as `1.26` (Go).
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.test` to `go test ./...` from `go.mod` after deterministic escalation.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Downgrade guard

A prior verified status was preserved because no previously present field regressed in this refresh.
