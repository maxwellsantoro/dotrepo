# Evidence

- Imported repository name from README.md.
- Imported maintainer candidates from CODEOWNERS. Maintainer information was imported from broad CODEOWNERS patterns; `owners.team` prefers `@nats-io/server` from the repo-wide rule, and `owners.maintainers` preserves narrower owner candidates.
- Inferred repo.build from go.mod as `go build ./...`.
- Left `repo.test` unset because `.github/workflows/long-tests.yaml` and `.github/workflows/mqtt-test.yaml` suggested conflicting test commands.
- Imported repo.toolchain.min from go.mod as `1.26.0` (Go).
- This is an overlay record, not a maintainer-controlled canonical record.

- Deepened `owners.security_contact` from `README.md` during deterministic escalation.
- Set `repo.name` to `nats-server` from `GitHub API` after deterministic escalation.
- Set `repo.test` to `go test ./...` from `go.mod` after deterministic escalation.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
