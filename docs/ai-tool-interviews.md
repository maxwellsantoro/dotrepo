# AI Coding Tool Interview Takeaways

This doc captures the current working takeaways from a 12-model interview round
on dotrepo's live public surface, protocol story, and likely adoption path.
It is not a benchmark or compatibility promise. It is product input for what
should happen next.

Public-facing synthesis:
[`https://dotrepo.org/writing/what-the-ais-think-about-dotrepo/`](https://dotrepo.org/writing/what-the-ais-think-about-dotrepo/)

## What landed well

- The live public JSON surface exists and is already trust-aware.
- Same-origin query responses return values together with selection, provenance,
  and conflict context instead of pretending fields are context-free facts.
- Freshness metadata is explicit enough for humans, agents, and caches to reason
  about staleness.

## Where the interviews converged

### 1. Grow the index until checking dotrepo is cheap

The biggest near-term gap is not protocol shape. It is data coverage. A tiny
index proves the architecture but does not yet make dotrepo the obvious first
check for arbitrary repositories.

Working target:

- first tranche: 50 reviewed high-signal overlays across Rust, TypeScript,
  Python, and Go
- follow-on tranche: 500 reviewed overlays before treating the service as a
  likely first-check lookup for common public repos

### 2. Add remote lookup to MCP

The hosted HTTP surface already supports URL-shaped remote lookup through
predictable repository paths under `https://dotrepo.org/v0/repos/...`.
The missing ergonomic layer is an MCP tool, such as `dotrepo.lookup`, that
takes a repository URL or identity and resolves against the hosted public
surface without cloning first.

### 3. Keep the core small while those two land

The trust model, freshness semantics, and query surface are the current
differentiators. Search, ranking, mutation, and heavier editor product work
should remain subordinate until the index is broader and remote lookup exists.

## What that means for the current roadmap

- treat the public contract as maintenance-mode unless a real compatibility gap
  appears
- prioritize seed-index growth and MCP remote lookup ahead of broader surface
  expansion
- keep the public site honest about what query responses return and what is
  still missing

## Current caveat

The checked-in seed index is still small and Rust-heavy. That is acceptable for
launching the protocol and public surface, but it is not yet enough to justify
dotrepo as a likely first check for arbitrary repositories encountered by
coding agents.
