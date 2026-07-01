# Evidence

- Imported repository description from README.md.
- Imported SECURITY.md, but no explicit contact channel was parsed, so security_contact = "unknown" is intentional.
- Inferred fallback values for `repo.name` because the imported files did not provide enough structured metadata.
- Inferred repo.build from .github/workflows/web.yml as `pnpm run build`.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Auto-promotion

Record auto-promoted to verified: all fields are honestly resolved by deterministic promotion scoring.
