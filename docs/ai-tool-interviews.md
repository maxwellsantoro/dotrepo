# AI Coding Tool Interview Takeaways

This document preserves the product lessons from a 9-model, 12-session
interview round on dotrepo's public surface, protocol, and adoption path. It is
product input, not a benchmark or compatibility promise.

Public-facing synthesis:
[`What the AIs think about dotrepo`](https://dotrepo.org/writing/what-the-ais-think-about-dotrepo/)

## What landed well

- The public JSON surface is real, stable, and trust-aware.
- Query responses return selection, provenance, freshness, and conflict context
  instead of presenting repository claims as context-free facts.
- The protocol gives agents a cheap first check before they spend resources
  cloning, scraping, and interpreting a repository again.

## What the interviews correctly prioritized

### Broader index coverage

The original interviews identified coverage as the primary product constraint.
That remains true, but the operating model is now autonomous rather than a
queue of human-reviewed records. The first tranche is complete; the next
milestone is useful, honestly scored coverage across a broader technology mix.

### Remote agent lookup

The hosted HTTP surface and MCP `dotrepo.lookup` path now provide remote lookup
without cloning first. This closed the largest ergonomic gap identified by the
interviews.

### A small, trustworthy core

Trust, freshness, provenance, and conflict semantics remain the foundation.
New surfaces should reuse those contracts instead of creating a parallel truth
model.

## Current implications

- Make the autonomous index factory observable, bounded, and cheap.
- Resolve deterministic evidence first and escalate only unresolved fields to
  progressively stronger models.
- Harden existing records while expanding coverage.
- Use the compact research profile and batch lookup contracts so one indexed
  result can replace repeated repository scraping across many agent sessions.
- Treat discovery and ranking as products built on trusted profiles, not as a
  substitute for profile quality.

## Current caveat

The index is large enough to demonstrate the system, but not yet broad enough
to be a dependable first check for arbitrary public repositories. Status counts
also do not measure usefulness by themselves: field completeness, evidence
quality, freshness, language diversity, and low-cost reproducibility matter.

See [`ROADMAP.md`](../ROADMAP.md) for product direction and active execution.
