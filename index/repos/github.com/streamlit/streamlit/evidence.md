# Evidence

- Imported repository docs entry points from README.md.
- Imported maintainer candidates from CODEOWNERS. Maintainer information was imported from CODEOWNERS; `owners.team` is `@streamlit/open-source-release-team` because it is the clearest imported team signal, but `owners.maintainers` still preserves narrower owner candidates.
- Imported the security reporting channel from SECURITY.md. SECURITY.md provided a policy or reporting URL rather than a direct mailbox, so `security_contact` preserves that URL.
- Inferred fallback values for `repo.name` because the imported files did not provide enough structured metadata.
- Imported repo.build from frontend/app/package.json as `npm run build`.
- Imported repo.test from frontend/app/package.json as `npm test`.
- Imported repo.toolchain.min from lib/pyproject.toml as `3.10` (Python).
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
