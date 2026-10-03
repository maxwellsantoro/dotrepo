# Evidence

- Imported repository name and docs entry points from README.md.
- Imported the security reporting channel from SECURITY.md. SECURITY.md provided a policy or reporting URL rather than a direct mailbox, so `security_contact` preserves that URL.
- Inferred fallback values for `repo.description` because the imported files did not provide enough structured metadata.
- Imported repo.build from package.json as `npm run build`.
- Inferred repo.test from .github/workflows/typescript.yml as `npm test --if-present`.
- Imported repo.toolchain.min from src/fetch/pyproject.toml as `3.10` (Python).
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Documentation correction (2026-09-21T04:36:55.205964Z)

- Withheld docs.getting_started; rejected `https://docs.astral.sh/uv/getting-started/installation/` because uv package-manager installation is not a getting-started guide for the server collection. Source: [README.md:77](https://github.com/modelcontextprotocol/servers/blob/d73f99efbfd40c3aa1b61e88728b3d49fb52608f/README.md#L77). No replacement was established by this correction.
- This documentation-only correction advances the record timestamp. Older assessments for other fields retain their original check times and are invalidated by public export until fresh verification; their values were not refreshed.
- This is an overlay record, not a maintainer-controlled canonical record.
