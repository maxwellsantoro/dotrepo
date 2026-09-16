# Evidence

- Imported repository name and docs entry points from README.md.
- Imported maintainer candidates from CODEOWNERS. Maintainer information was imported from broad CODEOWNERS patterns with multiple team owners, so `owners.team` was left unset and `owners.maintainers` preserves the competing owner candidates.
- Imported the security reporting channel from SECURITY.md. SECURITY.md provided a policy or reporting URL rather than a direct mailbox, so `security_contact` preserves that URL.
- Inferred repo.build from .github/workflows/build.yml as `npm run build`.
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.name` to `server` from `GitHub API` after deterministic escalation.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Security contact normalization (2026-07-08)

Replaced non-actionable `security_contact` value `https://bitwarden.com/contact` with `unknown`. The prior URL was not an email or actionable vulnerability-reporting surface (promotion scoring: medium-present). Honest absence unblocks auto-publish without inventing a reporting channel.

## Auto-promotion

Record auto-promoted to verified: all fields are honestly resolved by deterministic promotion scoring.

## Security contact evidence refresh (2026-09-16)

- Replaced `owners.security_contact = "unknown"` with `https://hackerone.com/bitwarden/`.
- Source: [SECURITY.md at `2294b786bc771290059137468d1ec3b1fc2c71c2`](https://github.com/bitwarden/server/blob/2294b786bc771290059137468d1ec3b1fc2c71c2/SECURITY.md), fetched at the pinned commit on 2026-09-16.
- The policy explicitly identifies `https://hackerone.com/bitwarden/` as a vulnerability reporting channel.
- This is a field-scoped correction supported by the above evidence, not a full repository recrawl. Existing crawl timestamps and GitHub head metadata describe the earlier full crawl. This supersedes the earlier contact-absence conclusion; record authority is unchanged.
