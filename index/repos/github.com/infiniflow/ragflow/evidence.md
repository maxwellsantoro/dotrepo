# Evidence

- Imported repository name from README.md.
- Ignored component-scoped commands from `web/package.json` as repository defaults.
- Inferred repo.build from go.mod as `go build ./...`.
- Left `repo.test` unset because `pyproject.toml` and `go.mod` suggested conflicting test commands.
- Imported repo.toolchain.min from pyproject.toml as `3.13` (Python).
- Conflicting documentation declarations in README.md; abstained from docs.root.
- Conflicting documentation declarations in README.md; abstained from docs.getting_started.
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.name` to `ragflow` from `GitHub API` after deterministic escalation.
- Left `repo.test` unset after deterministic escalation: no unique build/test candidate after deterministic tier walk. Preserved 2 candidate command(s) in `repo.test_candidates` instead of discarding them.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
