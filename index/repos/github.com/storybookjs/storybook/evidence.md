# Evidence

- Imported repository name and docs entry points from README.md.
- Imported maintainer candidates from CODEOWNERS.
- Imported the security reporting channel from SECURITY.md. SECURITY.md provided a policy or reporting URL rather than a direct mailbox, so `security_contact` preserves that URL.
- Imported repo.test from package.json as `yarn test`.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Security contact normalization (2026-07-08)

Replaced non-actionable `security_contact` value `https://x.com/storybookjs` with `unknown`. The prior URL was not an email or actionable vulnerability-reporting surface (promotion scoring: medium-present). Honest absence unblocks auto-publish without inventing a reporting channel.

## Auto-promotion

Record auto-promoted to verified: all fields are honestly resolved by deterministic promotion scoring.

## Security contact evidence refresh (2026-09-16)

- Replaced `owners.security_contact = "unknown"` with `https://github.com/storybookjs/storybook/security/advisories/new`.
- Source: [SECURITY.md at `4f66ceeb2410de4bcefe3ba3919267495cc40f37`](https://github.com/storybookjs/storybook/blob/4f66ceeb2410de4bcefe3ba3919267495cc40f37/SECURITY.md), fetched at the pinned commit on 2026-09-16.
- The policy explicitly directs private GitHub advisory reporting. The read-only GitHub API `GET /repos/storybookjs/storybook/private-vulnerability-reporting` returned `{"enabled":true}` on 2026-09-16. Resolved the documented repository reporting workflow to `https://github.com/storybookjs/storybook/security/advisories/new`.
- This is a field-scoped correction supported by the above evidence, not a full repository recrawl. Existing crawl timestamps and GitHub head metadata describe the earlier full crawl. This supersedes the earlier contact-absence conclusion; record authority is unchanged.
