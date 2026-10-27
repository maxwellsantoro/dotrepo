# Evidence

- Imported repository name and docs entry points from README.md.
- Inferred fallback values for `repo.description` because the imported files did not provide enough structured metadata.
- Ignored component-scoped commands from `bindings/datasette/setup.py` as repository defaults.
- Imported repo.test from Makefile as `make test`.
- Imported docs.root as `./docs.md`. Explicit documentation link at README.md:93: See [`docs.md`](./docs.md) for a instructions to compile `sqlite-vss` yourself, as well as a full SQL API reference.
- Discovered related relation to github.com/asg017/sqlite-vec from README cross-link.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Auto-promotion

All fields are high-confidence present or high-confidence absent. Record auto-promoted to verified status.
