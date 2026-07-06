# Evidence

- Imported repository name from README.md.
- Imported repo.build from Makefile as `go build -gcflags='all=-N -l'`.
- Left `repo.test` unset because `Makefile` and `justfile` suggested conflicting test commands.
- Imported repo.toolchain.min from go.mod as `1.25.0` (Go).
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.name` to `lazygit` from `GitHub API` after deterministic escalation.
- Set `repo.test` to `go test ./... -short -cover -args "-test.gocoverdir=/tmp/code_coverage"` from `.github/workflows/ci.yml` after deterministic escalation.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Downgrade guard

A prior verified status was preserved because no previously present field regressed in this refresh.
