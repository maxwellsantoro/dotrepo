# Claim review

- Claim: `github.com/maxwellsantoro/ries-rs/2026-03-16-maintainer-claim-01`
- Repository: `github.com/maxwellsantoro/ries-rs`
- Status: `Accepted`
- Reviewer: `index-reviewer`
- Decision: Accepted and linked to published canonical `.repo`.
- Notes:
  - The claimant matches the public repository owner `@maxwellsantoro`.
  - This is a maintainer-owned bootstrap claim for the first live accepted maintainer-claim example checked into the seed index.
  - The upstream repository now has a public `v1.0.1` release with CLI, WASM, and Python artifacts, so this claim is tied to a shipped public repo rather than a pre-release draft.
  - The upstream repository now publishes a native `.repo`, so the corrected accepted claim links to that canonical record and the derived handoff is `superseded`.
  - The checked-in seed index remains overlay-only today, so the public export still shows the reviewed overlay as visible seed-index context rather than an index-side canonical mirror.
  - A second independently reviewed example is still desirable, but this closes the staged-only gap in the live index.
