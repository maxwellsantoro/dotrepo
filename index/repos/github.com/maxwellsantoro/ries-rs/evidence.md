# Evidence

- Imported repository name from README.md.
- Imported maintainer candidates from CODEOWNERS.
- Imported the security reporting channel from SECURITY.md. SECURITY.md provided a policy or reporting URL rather than a direct mailbox, so `security_contact` preserves that URL.
- Imported repo.build from package.json as `npm run build`.
- Imported repo.test from package.json as `npm test`.
- Imported repo.toolchain.min from ries-py/pyproject.toml as `3.8` (Python).
- Discovered related relation to github.com/maxwellsantoro/ries-rs from Cargo.toml repository.
- Discovered related relation to github.com/clsn/ries from README cross-link.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Auto-promotion

All fields are high-confidence present or high-confidence absent. Record auto-promoted to verified status.

## October 4, 2026 command correction

This appendix supersedes the package.json command imports and their prior
verified assessments above. The own-project study pinned public snapshot
`ed6e31ffa157cd6c96e8ff907a97ce1f707e059784e417b2bbf87ffaba931488` before any correction;
its paired observations and unfavorable results remain unchanged.

At this record's retained upstream revision
`0904c3ed17d2f221ea565a7b9e15929d9fe8b419`, package.json build/test scripts target
WASM. The maintainer's root `.repo` explicitly declares `cargo build --release --locked`
and `cargo nextest run --tests --locked` as repository defaults. Those exact
entrypoints replace the WASM scalars. This correction does not make a canonical
mirror or assert that every language/binding surface is built or tested.

The command assessments are removed and verified status is downgraded to
imported pending complete verification. The record timestamp and all unrelated
field assessments remain unchanged. Existing claim events and canonical links
are preserved. No npm instruction was executed in the study; the runner recorded
accepted context mismatches and fell back to the frozen Rust instructions.

[The retained packet](../../../../../benchmarks/head-to-head/results/own-projects-2026-10-04/README.md)
contains original profile/record bytes, both pinned upstream sources, their
hashes, source URLs, and the study's execution logs. The source inspection after
all paired runs is separate from the study's timed observations.
