# Evidence

- Imported repository name and docs entry points from README.md.
- Imported maintainer candidates from CODEOWNERS.
- Imported the security reporting channel from SECURITY.md. SECURITY.md provided a policy or reporting URL rather than a direct mailbox, so `security_contact` preserves that URL.
- Left `repo.build` unset because `.github/workflows/js-and-wasm-artifacts.yml` and `.github/workflows/lagom-template.yml` suggested conflicting build commands.
- Inferred repo.test from Cargo.toml as `cargo test --workspace`.
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.build` to `-DCMAKE_C_COMPILER=clang \` from `.github/workflows/js-and-wasm-artifacts.yml` after deterministic escalation.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Security contact normalization (2026-07-08)

Replaced non-actionable `security_contact` value `https://github.com/LadybirdBrowser/ladybird/issues/new?template=bug_report.yml` with `unknown`. The prior URL was not an email or actionable vulnerability-reporting surface (promotion scoring: medium-present). Honest absence unblocks auto-publish without inventing a reporting channel.

## Auto-promotion

Record auto-promoted to verified: all fields are honestly resolved by deterministic promotion scoring.

## Security contact evidence refresh (2026-09-16)

- Replaced `owners.security_contact = "unknown"` with `https://github.com/LadybirdBrowser/ladybird/security/advisories/new`.
- Source: [SECURITY.md at `9425ccfac4061c8d5cc8bd5db7e6dfa4a6eac135`](https://github.com/LadybirdBrowser/ladybird/blob/9425ccfac4061c8d5cc8bd5db7e6dfa4a6eac135/SECURITY.md), fetched at the pinned commit on 2026-09-16.
- The policy explicitly directs private GitHub advisory reporting. The read-only GitHub API `GET /repos/LadybirdBrowser/ladybird/private-vulnerability-reporting` returned `{"enabled":true}` on 2026-09-16. Resolved the documented repository reporting workflow to `https://github.com/LadybirdBrowser/ladybird/security/advisories/new`.
- This is a field-scoped correction supported by the above evidence, not a full repository recrawl. Existing crawl timestamps and GitHub head metadata describe the earlier full crawl. This supersedes the earlier contact-absence conclusion; record authority is unchanged.
