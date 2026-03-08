# Rebuild plan

## Immediate goals

1. Establish dotrepo as a protocol + reference toolchain + public index.
2. Tighten the v0.1 schema around a single canonical in-repo form.
3. Add first-class queryability for tools and agents.
4. Make trust, provenance, and overlay status central rather than incidental.
5. Keep public messaging balanced: inspiring, but concrete and careful.

## Top-level build order

### Phase 1 — Spec lock
- Finalize the v0.1 `.repo` file shape
- Finalize trust ladder terminology
- Finalize overlay record format for the index
- Finalize CLI contract including `query`
- Reserve extension and relations namespaces

### Phase 2 — Reference toolchain
- Parser and schema validation
- Mode-aware validation for native vs overlay
- Query engine
- README and compatibility surface generation
- Drift / doctor checks

### Phase 3 — Ecosystem surfaces
- GitHub Actions
- VS Code extension and LSP
- MCP server
- Example repos and import flows

### Phase 4 — Index
- Git-backed index repo shape
- PR workflow and automated review checks
- Trust and provenance surfacing
- Claiming flow for maintainers

## Design guardrails

- Do not over-promise full arbitrary round-tripping.
- Do not let the core schema become a kitchen sink.
- Do not blur inferred and canonical data.
- Do not optimize only for one side of the ecosystem.
- Do not undermine trust by being vague about provenance.
