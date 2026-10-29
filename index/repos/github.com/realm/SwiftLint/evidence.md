# Evidence

- Imported repository name and docs entry points from README.md.
- Imported repo.build from Makefile as `make all`.
- Imported repo.test from Makefile as `make test`.
- Imported docs.root as `https://megalinter.io/latest/descriptors/swift_swiftlint/`. Explicit documentation link at README.md:486: [SwiftLint documentation](https://megalinter.io/latest/descriptors/swift_swiftlint/)
- Discovered related relation to github.com/github/swift-style-guide from README cross-link.
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


## Bounded F1 documentation association correction — 2026-10-29

Earlier import and auto-promotion paragraphs above are retained as historical evidence. This dated correction supersedes the selected `docs.root` value and withdraws the whole-record verified claim.

- Previous value: `https://megalinter.io/latest/descriptors/swift_swiftlint/`. Its source association is to the named integration/client task, not this repository documentation entrypoint.
- Corrected value: `https://realm.github.io/SwiftLint/index.html`.
- Source: https://github.com/realm/SwiftLint/blob/ec4691d9e813a1d3358e82917326b56b0a71d3c9/README.md, revision `ec4691d9e813a1d3358e82917326b56b0a71d3c9`, README SHA256 `b1490448cf43b1319e87686239617bc8dfe6f60b725ed9cb8f81b326d124c534`, Git blob `4bb2c15642cc0bd5352294931d95ac1268c0c355`.
- Assessment: Pinned README lines 482-487 identifies the old URL as MegaLinter aggregator integration setup, not the project documentation entrypoint. README lines 606-607 declares the SwiftLint Rule Directory; its retained HTTP200 page links index.html as the documentation header/breadcrumb, and the retained HTTP200 index identifies SwiftLintCore Docs, links realm/SwiftLint and renders the SwiftLint overview. The replacement resolves that declared navigation link exactly. Target pages are mutable observations; source-commit/version parity is not established.
- Target/source observations: README.md:606–607 → https://realm.github.io/SwiftLint/rule-directory.html (HTTP 200, SHA256 c1d6ef04e87845f2c6e541a27c1b2ae011a868389d717dfbeb995169bdc32226) → header/breadcrumb index.html → https://realm.github.io/SwiftLint/index.html (HTTP 200, SHA256 bf89bac5f9749fa1c172ba65013fa43840b50225660602ebd114ad47ac9081fb). No redirect was followed. The index identifies SwiftLintCore 0.65.1 Docs and links this repository; no version parity is claimed.
- Field evidence checked at `2026-10-29T08:36:31.832479Z` and bound to the exact replacement value. Raw sources, request timings, before/after hashes, limitations and dispositions: `index/telemetry/f1-docs-association-20261029/`.
- Record downgraded from automated verified to imported with medium record trust. Remaining fields were not reinspected, their old evidence timestamps are retained, and `generated_at = 2026-10-27T18:15:27.41844Z` is unchanged; this does not reset whole-record factual age. No upstream command execution or maintainer review was performed.

This is an overlay record, not a maintainer-controlled canonical record.
