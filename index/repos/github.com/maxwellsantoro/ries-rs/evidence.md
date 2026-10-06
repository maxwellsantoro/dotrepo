# Source inspection, October 5, 2026

Checked at `2026-10-06T01:15:26.806051Z` against upstream revision `cfa959ed21a5a5e5f3d9538d9d1714c2401611e5`.

- Imported repository name/description from the pinned README and license from the license files/Cargo declaration. Homepage is the inspected repository identity.
- Build/test selection: CONTRIBUTING labels cargo build as the core crate/CLI loop. AGENTS gives cargo test as the core Rust loop alternative to nextest and maps core/runtime ownership to src. Both run from the root Cargo package and cover the Rust core/CLI, not the Python and WASM packaging surfaces. Prior uninspected metadata and stale scalar assessments are omitted rather than rejuvenated. Claim history and canonical links are unchanged.
- No docs.root is asserted: this bounded refresh did not inspect a complete documentation-root contract. No unknown placeholder is used for absent ownership/security fields.
- Whole command candidates have exact JSON value and check-time bindings. Prerequisites are descriptions, not shell commands or execution authorization.

- [README.md](https://github.com/maxwellsantoro/ries-rs/blob/cfa959ed21a5a5e5f3d9538d9d1714c2401611e5/README.md) SHA-256 `19b0b7d34cd0ff2644aeb15f7f9ae4044e84b0c91470c685df6a1cff751ccadd`.
- [CONTRIBUTING.md](https://github.com/maxwellsantoro/ries-rs/blob/cfa959ed21a5a5e5f3d9538d9d1714c2401611e5/CONTRIBUTING.md) SHA-256 `043dd0e848ff8ed4be6870d3072110a3dca786fa2e6e12a35743afff32816381`.
- [AGENTS.md](https://github.com/maxwellsantoro/ries-rs/blob/cfa959ed21a5a5e5f3d9538d9d1714c2401611e5/AGENTS.md) SHA-256 `66a187844b884767690b2a25939e2a3e29ae00a90ebca23c89a9cc17d13b76e5`.
- [Cargo.toml](https://github.com/maxwellsantoro/ries-rs/blob/cfa959ed21a5a5e5f3d9538d9d1714c2401611e5/Cargo.toml) SHA-256 `4da2591803c192683841b15cd6be1f4e141444054a7132b938786de63668fc08`.
- [LICENSE](https://github.com/maxwellsantoro/ries-rs/blob/cfa959ed21a5a5e5f3d9538d9d1714c2401611e5/LICENSE) SHA-256 `dc54197df320bb3ec3bfe59247fc6817fe2806ee9e9ae1780367601844e06523`.

This is an overlay record, not a maintainer-controlled canonical record.

## Historical evidence (superseded; retained verbatim)

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
