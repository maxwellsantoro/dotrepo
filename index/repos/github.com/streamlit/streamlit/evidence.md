# Evidence

- Imported repository docs entry points from README.md.
- Imported maintainer candidates from CODEOWNERS. Maintainer information was imported from CODEOWNERS; `owners.team` is `@streamlit/open-source-release-team` because it is the clearest imported team signal, but `owners.maintainers` still preserves narrower owner candidates.
- Imported the security reporting channel from SECURITY.md. SECURITY.md provided a policy or reporting URL rather than a direct mailbox, so `security_contact` preserves that URL.
- Inferred fallback values for `repo.name` because the imported files did not provide enough structured metadata.
- Ignored component-scoped commands from `frontend/app/package.json` as repository defaults.
- Ignored component-scoped commands from `lib/pyproject.toml` as repository defaults.
- Imported repo.build from Makefile as `make all`.
- Imported repo.test from Makefile as `make check`.
- Imported repo.toolchain.min from lib/pyproject.toml as `3.11` (Python).
- Imported docs.root as `https://docs.streamlit.io`. Explicit documentation link at README.md:123: - Explore our [docs](https://docs.streamlit.io) to learn how Streamlit works.
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
