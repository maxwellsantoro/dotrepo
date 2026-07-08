# Evidence

- Imported repository name from README.md.
- Imported maintainer candidates from CODEOWNERS.
- Imported the security reporting channel from SECURITY.md. SECURITY.md provided a policy or reporting URL rather than a direct mailbox, so `security_contact` preserves that URL.
- Inferred fallback values for `repo.description` because the imported files did not provide enough structured metadata.
- Imported repo.build from Makefile as `make build`.
- Imported repo.test from Makefile as `make test`.
- Imported repo.toolchain.min from go.mod as `1.23.0` (Go).
- Discovered related relation to github.com/jdx/mise from README cross-link.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Security contact normalization (2026-07-08)

Replaced non-actionable `security_contact` value `https://github.com/junegunn/fzf` with `unknown`. The prior URL was not an email or actionable vulnerability-reporting surface (promotion scoring: medium-present). Honest absence unblocks auto-publish without inventing a reporting channel.

## Auto-promotion

Record auto-promoted to verified: all fields are honestly resolved by deterministic promotion scoring.
