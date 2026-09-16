# Evidence

- Imported repository name from README.md.
- Imported the security reporting channel from SECURITY.md. SECURITY.md provided a policy or reporting URL rather than a direct mailbox, so `security_contact` preserves that URL.
- Left `repo.build` unset because `.github/workflows/ci.yml` suggested an unsafe shell-like command.
- Left `repo.test` unset because `.github/workflows/ci.yml` suggested an unsafe shell-like command.
- Imported repo.toolchain.min from Cargo.toml as `1.95.0` (Rust).
- Discovered related relation to github.com/nushell/nushell from Cargo.toml repository.
- Discovered related relation to github.com/marketplace/actions from README cross-link.
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.build` to `cargo build --workspace` from `Cargo.toml` after deterministic escalation.
- Set `repo.test` to `cargo test --workspace` from `Cargo.toml` after deterministic escalation.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Security contact normalization (2026-07-08)

Replaced non-actionable `security_contact` value `https://discord.gg/NtAbbGn` with `unknown`. The prior URL was not an email or actionable vulnerability-reporting surface (promotion scoring: medium-present). Honest absence unblocks auto-publish without inventing a reporting channel.

## Auto-promotion

Record auto-promoted to verified: all fields are honestly resolved by deterministic promotion scoring.

## Security contact evidence refresh (2026-09-16)

- Replaced `owners.security_contact = "unknown"` with `https://github.com/nushell/nushell/security/advisories/new`.
- Source: [SECURITY.md at `0667685083650a32d4affc0303584fc1cf20888a`](https://github.com/nushell/nushell/blob/0667685083650a32d4affc0303584fc1cf20888a/SECURITY.md), fetched at the pinned commit on 2026-09-16.
- The policy explicitly identifies `https://github.com/nushell/nushell/security/advisories/new` as a vulnerability reporting channel.
- This is a field-scoped correction supported by the above evidence, not a full repository recrawl. Existing crawl timestamps and GitHub head metadata describe the earlier full crawl. This supersedes the earlier contact-absence conclusion; record authority is unchanged.
