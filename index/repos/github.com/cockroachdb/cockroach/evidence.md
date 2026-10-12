# Evidence

- Imported repository docs entry points from README.md.
- Imported maintainer candidates from CODEOWNERS. Maintainer information was imported from broad CODEOWNERS patterns with multiple team owners, so `owners.team` was left unset and `owners.maintainers` preserves the competing owner candidates.
- Inferred fallback values for `repo.name` because the imported files did not provide enough structured metadata.
- Imported repo.build from GNUmakefile as `make build`.
- Imported repo.test from GNUmakefile as `make test`.
- Imported repo.toolchain.min from go.mod as `1.26.2` (Go).
- Imported docs.root as `https://cockroachlabs.com/docs/stable/`. Explicit documentation link at README.md:36: For guidance on installation, development, deployment, and administration, see our [User Documentation](https://cockroachlabs.com/docs/stable/).
- Imported docs.getting_started as `https://www.cockroachlabs.com/docs/cockroachcloud/quickstart.html`. Explicit documentation link at README.md:42: See our online documentation: [Quickstart with CockroachCloud](https://www.cockroachlabs.com/docs/cockroachcloud/quickstart.html)
- Discovered related relation to github.com/cockroachdb/cockroach from README cross-link.
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
