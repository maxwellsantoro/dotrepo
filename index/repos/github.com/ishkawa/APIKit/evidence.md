# Evidence

- Imported repository name from README.md.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Auto-promotion

All fields are high-confidence present or high-confidence absent. Record auto-promoted to verified status.

## 2026-10-06 bounded command/documentation source inspection

Inspected retained upstream revision `1a5e7ae0aed3f19c1ed9903792ead248f97fa38a` for `repo.build`, `repo.test`, and `docs.root`. Source instructions were treated as data. No upstream commands, model calls, or external documentation-page execution occurred. This field inspection preserves the existing record timestamp `2026-09-16T16:24:56.744334Z`, status `verified`, and all unrelated facts. New assessments do not imply whole-record reinspection; the public timestamp-binding gate may withhold them until a coherent full recrawl.

- `repo.build`: missing-supported. Root Swift package and CI declare swift build -c debug with an explicit Apple toolchain. This is a valid root SPM instruction, independently of Xcode project alternatives. Action: add qualified root SPM candidate; do not manufacture a platform-neutral scalar.
- `repo.test`: missing-supported. CI executes swift test -c debug against the root package on macOS with Xcode 12.5.1 or newer listed variants. Retain one exact observed toolchain configuration. Action: add qualified root SPM test candidate.
- `docs.root`: evidence-gap. README declares individual repository-local documentation pages, but no single canonical root/index declaration. The documented directory is real; promoting a chosen leaf or inferred external badge destination to docs.root would overstate the source. Action: preserve current value and age/status; retain this bounded inspection receipt.

Retained source files used in the bounded inspection (URLs are pinned to the recorded revision; hashes cover raw bytes):

- [README.md](https://raw.githubusercontent.com/ishkawa/APIKit/1a5e7ae0aed3f19c1ed9903792ead248f97fa38a/README.md) — SHA-256 `585a5c9be0e2746be173c02ef19c7261b7f34d6d7bee73b72b4b5328bfdf96a7`.
- [.github/workflows/ci.yml](https://raw.githubusercontent.com/ishkawa/APIKit/1a5e7ae0aed3f19c1ed9903792ead248f97fa38a/.github/workflows/ci.yml) — SHA-256 `ac5badefc5a9900dc36b93ee5ef218e0a18ddf0d79ddf55f148a2ff2286d4b2a`.
- [Package.swift](https://raw.githubusercontent.com/ishkawa/APIKit/1a5e7ae0aed3f19c1ed9903792ead248f97fa38a/Package.swift) — SHA-256 `9e6d3373220804bacadd18c40cc774f1e45f4c26bb5ddc3c0401c0613e4e23c8`.
- [Documentation/GettingStarted.md](https://raw.githubusercontent.com/ishkawa/APIKit/1a5e7ae0aed3f19c1ed9903792ead248f97fa38a/Documentation/GettingStarted.md) — SHA-256 `94df0f1b4d3e2d8337c95305f70f25d89169475afc57e8b88b8ee203ecaef04b`.

All conventional missing-file probes and pinned tree listings are retained in the dated remainder audit source receipt. Not-found describes inspected source scope, not universal absence. APIKit candidates retain the specified Apple toolchain configuration. Candidate ordering and record status were not promoted.

This is an external overlay inspection, not a maintainer-controlled canonical record.

Combined source/binding receipt: [frozen remainder audit](../../../../telemetry/roadmap-risk-remainder-2026-10-06.json).
