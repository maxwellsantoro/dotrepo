# Evidence

- Imported repository name and docs entry points from README.md.
- Imported maintainer candidates from CODEOWNERS. Maintainer information was imported from broad CODEOWNERS patterns with multiple team owners, so `owners.team` was left unset and `owners.maintainers` preserves the competing owner candidates.
- Ignored component-scoped commands from `ui/packages/consul-ui/package.json` as repository defaults.
- Imported repo.build from Makefile as `make all`.
- Imported repo.test from Makefile as `make test`.
- Imported repo.toolchain.min from ui/packages/consul-ui/package.json as `24` (Node.js).
- Imported docs.root as `https://developer.hashicorp.com/consul/docs`. Explicit documentation link at README.md:62: Full, comprehensive documentation is available on the Consul website: https://developer.hashicorp.com/consul/docs
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
