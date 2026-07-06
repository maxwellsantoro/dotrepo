# Evidence

- Imported repository name and docs entry points from README.md.
- Imported repo.build from README.md as `make`.
- Left `repo.test` unset because `.github/workflows/code-checker.yaml` suggested an unsafe shell-like command.
- Imported repo.toolchain.min from go.mod as `1.26.4` (Go).
- Discovered related relation to github.com/milvus-io/milvus from README cross-link.
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
