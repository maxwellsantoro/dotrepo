# Evidence

- Imported SECURITY.md, but no explicit contact channel was parsed, so security_contact = "unknown" is intentional.
- Inferred fallback values for `repo.name` because the imported files did not provide enough structured metadata.
- Inferred repo.build from .github/workflows/web.yml as `pnpm run build`.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Downgrade guard

A prior verified status was preserved because no previously present field regressed in this refresh.

## Security contact evidence refresh (2026-09-16)

- Replaced `owners.security_contact = "unknown"` with `https://github.com/chaitin/PandaWiki/security/advisories`.
- Source: [SECURITY.md at `9ab7d6f95dfc38a10019e8a5903743e3e7a84ae1`](https://github.com/chaitin/PandaWiki/blob/9ab7d6f95dfc38a10019e8a5903743e3e7a84ae1/SECURITY.md), fetched at the pinned commit on 2026-09-16.
- The policy explicitly identifies `https://github.com/chaitin/PandaWiki/security/advisories` as a vulnerability reporting channel.
- This is a field-scoped correction supported by the above evidence, not a full repository recrawl. Existing crawl timestamps and GitHub head metadata describe the earlier full crawl. This supersedes the earlier contact-absence conclusion; record authority is unchanged.
