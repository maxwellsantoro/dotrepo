# Public export fixture pack

This fixture pack provides a small, reviewable source tree for the static public
export surface.

It covers two representative repository identities:

- `github.com/example/orbit`: a plain reviewed overlay with docs, team, and
  security-contact summary fields
- `github.com/example/nova`: a reviewed overlay with an accepted maintainer
  claim still in `pending_canonical` handoff state

The checked-in `expected/` tree is the golden-output surface for issue `#63`.
It is intended to catch:

- response-shape drift in bundle `repos/index.json`, repository `index.json`,
  `trust.json`, repo-scoped `query-input/*.json`, and snapshot `meta.json`
- claim-visibility drift for ordinary public repository responses
- unexpected changes to links, artifact locators, or summary-field mapping

The test gate fixes `generatedAt` / `staleAfter` and recomputes the deterministic
snapshot digest from `fixture-index/`, so changes to the source fixture tree are
reflected intentionally in the expected outputs.
