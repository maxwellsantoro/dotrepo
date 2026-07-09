# Evidence

- Imported repository name and docs entry points from README.md.
- Imported SECURITY.md, but no explicit contact channel was parsed, so security_contact = "unknown" is intentional.
- Inferred repo.build from go.mod as `go build ./...`.
- Left `repo.test` unset because `.github/workflows/sep-tests.yml` suggested an unsafe shell-like command.
- Imported repo.toolchain.min from pyproject.toml as `3.13` (Python).
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.name` to `ragflow` from `GitHub API` after deterministic escalation.
- Left `repo.test` unset after model escalation: The candidates represent mutually exclusive language ecosystems (Python vs Go); no single primary value can represent the repository.. Preserved 2 candidate command(s) in `repo.test_candidates` instead of discarding them.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Downgrade guard

A prior verified status was preserved because no previously present field regressed in this refresh.
