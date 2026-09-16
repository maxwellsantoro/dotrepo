# Evidence

- Imported repository name from README.md.
- Imported maintainer candidates from CODEOWNERS. Maintainer information was imported from broad CODEOWNERS patterns; `owners.team` prefers `@cli/code-reviewers` from the repo-wide rule, and `owners.maintainers` preserves narrower owner candidates.
- Imported the security reporting channel from SECURITY.md. SECURITY.md provided a policy or reporting URL rather than a direct mailbox, so `security_contact` preserves that URL.
- Inferred fallback values for `repo.description` because the imported files did not provide enough structured metadata.
- Inferred repo.build from go.mod as `go build ./...`.
- Imported repo.test from Makefile as `go test ./...`.
- Imported repo.toolchain.min from go.mod as `1.26.0` (Go).
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Security contact normalization (2026-07-08)

Replaced non-actionable `security_contact` value `https://pkg.go.dev/golang.org/x/vuln/cmd/govulncheck` with `unknown`. The prior URL was not an email or actionable vulnerability-reporting surface (promotion scoring: medium-present). Honest absence unblocks auto-publish without inventing a reporting channel.

## Auto-promotion

Record auto-promoted to verified: all fields are honestly resolved by deterministic promotion scoring.

## Security contact evidence refresh (2026-09-16)

- Replaced `owners.security_contact = "unknown"` with `https://hackerone.com/github`.
- Source: [.github/SECURITY.md at `0cf1092493af067646fc5f3db9421c6a6ec9c938`](https://github.com/cli/cli/blob/0cf1092493af067646fc5f3db9421c6a6ec9c938/.github/SECURITY.md), fetched at the pinned commit on 2026-09-16.
- The policy explicitly identifies `https://hackerone.com/github` as a vulnerability reporting channel.
- This is a field-scoped correction supported by the above evidence, not a full repository recrawl. Existing crawl timestamps and GitHub head metadata describe the earlier full crawl. This supersedes the earlier contact-absence conclusion; record authority is unchanged.
