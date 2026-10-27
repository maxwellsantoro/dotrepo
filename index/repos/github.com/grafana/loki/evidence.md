# Evidence

- Imported repository name and docs entry points from README.md.
- Imported maintainer candidates from CODEOWNERS. Maintainer information was imported from broad CODEOWNERS patterns; `owners.team` prefers `@grafana/loki-team` from the repo-wide rule, and `owners.maintainers` preserves narrower owner candidates.
- Imported repo.build from Makefile as `make all`.
- Imported repo.test from CONTRIBUTING.md as `make test`.
- Imported repo.toolchain.min from go.mod as `1.27.3` (Go).
- Imported docs.root as `https://grafana.com/docs/loki/latest/`. Explicit documentation link at README.md:47: * [Latest release](https://grafana.com/docs/loki/latest/)
- Imported docs.getting_started as `https://grafana.com/docs/loki/latest/get-started/`. Explicit documentation link at README.md:36: * [Getting Started](https://grafana.com/docs/loki/latest/get-started/)
- Discovered related relation to github.com/grafana/alloy from README cross-link.
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.name` to `loki` from `GitHub API` after deterministic escalation.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Auto-promotion

All fields are high-confidence present or high-confidence absent. Record auto-promoted to verified status.
