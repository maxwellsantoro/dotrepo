# RFC 0013: Phased maintainer-claim implementation plan

## Status
Draft

## Summary

This RFC breaks the maintainer-claim workflow into deliberate implementation
phases after the design surfaces in [`RFC 0008`](./0008-maintainer-claim-lifecycle.md)
through [`RFC 0012`](./0012-claim-history-and-superseded-overlay-visibility.md)
have been drafted.

The guiding rule is straightforward:
- do not jump from claim-workflow design directly to a full product surface
- stage the work through durable artifacts, read-only inspection, and reviewer
  operations first
- keep public-facing product flow later than the first trustworthy index-side
  workflow

This RFC is sequencing guidance. It does not start implementation by itself, and
it does not make staffing or schedule commitments.

## Why

The maintainer-claim track now has drafts for:
- lifecycle and actor roles
- claim record and audit artifacts
- overlay-to-canonical handoff states
- rejection, withdrawal, dispute, and correction rules
- claim-history and superseded-overlay visibility

That is enough design surface to stop hand-waving and sequence the work
deliberately.

Without phased planning, the project would risk:
- building a public-facing claim product before the index artifacts are
  validated
- adding maintainer-facing UX before read-only inspection exists
- mixing product workflow, site work, and protocol behavior into one jump
- over-promising authority handoff before the audit trail and visibility rules
  are executable

## Planning principles

### Artifact-first before product-first

The first implementation phases should make claim artifacts durable, valid, and
inspectable before they become a self-service product flow.

### Read-only before mutating workflow

Consumers and reviewers should be able to inspect claims safely before later
tools start creating or advancing claims automatically.

### Reviewer workflow before public claim surface

The first trustworthy release should support index operators and maintainers in a
Git-native review loop before the project adds broader public submission or site
workflow.

### No authority inflation

No phase should treat accepted claims as canonical authority by themselves or
permit field blending across authority boundaries.

## Preconditions

The phased implementation plan assumes:
- the current claim RFC set is stable enough to encode into validation rules
- the existing `selection` / `conflicts` contract remains the base model for
  record selection
- the repository identity path in the index remains the anchor for claim
  artifacts

If those assumptions change materially, this plan should be revisited.

## Phase 0: Design consolidation

This is the handoff point between draft design and executable work.

Scope:
- reconcile the lifecycle, audit, handoff, failure-path, and visibility drafts
- align terminology across the RFCs
- confirm example scenarios cover overlay-only, canonical-only, clean handoff,
  disputed, rejected, withdrawn, and corrected paths
- decide which pieces are normative enough to encode in validation

Exit criteria:
- the claim RFC set is internally consistent enough for schema and validation
  work
- the roadmap can point at a stable implementation order rather than open-ended
  exploration

## Phase 1: Durable artifacts and validation

This should be the first code-bearing phase.

Scope:
- define parseable claim and claim-event schemas in Rust
- load and validate `claim.toml`, `events/*.toml`, and optional `review.md`
  presence rules
- extend `validate-index` to check claim directory layout, identity alignment,
  event ordering, transition correctness, and handoff-state consistency
- add fixture coverage for accepted, pending, disputed, rejected, withdrawn, and
  corrected claim examples

Dependencies:
- settled lifecycle and audit artifact drafts
- settled handoff and failure-path state vocabulary

Exit criteria:
- claim directories can be checked into the index and validated deterministically
- malformed or inconsistent claim history fails in a reviewable way
- claim artifacts are no longer “docs only”

## Phase 2: Read-only inspection surfaces

This should make claim state visible without introducing mutating workflow.

Scope:
- add shared core report types for claim inspection
- add read-only CLI and MCP inspection surfaces for claim state and event history
- surface claim-aware visibility on top of existing `selection` / `conflicts`
  outputs where it materially explains record state
- document how superseded overlays and unresolved disputes appear in those
  read-only surfaces

Dependencies:
- Phase 1 validation and fixture coverage
- visibility rules from [`RFC 0012`](./0012-claim-history-and-superseded-overlay-visibility.md)

Exit criteria:
- users and agents can inspect claim history without reading raw claim files
- trust/query surfaces remain semantically aligned with the claim-inspection
  reports
- rejected, withdrawn, and corrected history remain visible through read-only
  inspection

## Phase 3: Reviewer workflow and handoff recording

This should be the first operational workflow phase.

Scope:
- add helpers for scaffolding claim directories and append-only events
- add reviewer-oriented commands or templates for moving claims through
  submitted, in-review, accepted, rejected, withdrawn, disputed, and corrected
  states
- make handoff outcomes (`pending_canonical`, `superseded`, `parallel`,
  `disputed`) recordable in a disciplined way
- extend docs and review checklists so index operators have one clear workflow

Dependencies:
- Phase 1 artifact validation
- Phase 2 inspection surfaces

Exit criteria:
- index operators can run a Git-native maintainer-claim review loop without
  bespoke manual conventions
- accepted claims and completed handoffs are recorded consistently
- the project has a trustworthy internal workflow before it opens a broader
  public flow

## Phase 4: Maintainer-facing product flow

This phase should stay later than the first reviewer-capable workflow.

Scope:
- claim submission UX for maintainers
- public-facing claim status surfaces
- optional site or API integration for claim history
- later identity-proof and notification integration, if the project still wants
  them

Dependencies:
- Phases 1 through 3 working reliably
- clearer product requirements for public index/site workflow

Exit criteria:
- maintainers can initiate and follow a claim through a stable product surface
- public-facing workflow does not outrun the underlying audit and visibility
  contract

## Recommended execution order

The next execution pass should sequence the maintainer-claim workflow this way:

1. artifact schemas and `validate-index` support
2. claim fixtures and regression coverage
3. read-only claim inspection in core, CLI, and MCP
4. claim-aware visibility in trust/query reporting
5. reviewer workflow helpers and checklists
6. only then broader maintainer-facing submission flow

This keeps correctness and inspection ahead of product UX.

## Explicit deferrals

The first claim-workflow release should defer:
- external identity or authentication providers
- automated canonical `.repo` generation
- silent backfill from superseded overlays into canonical records
- public site ranking or discovery features built around claims
- bundle/workspace/relations integration
- editor-specific claim authoring or review UX

Those are real later concerns, but they should not block the first trustworthy
index-side claim workflow.

## Relationship to the roadmap

Within the current roadmap shape:
- `v0.3c` should begin with Phases 1 through 3
- public-facing claim UX belongs after those phases have proven stable
- public index site and query API work should not assume claim-product maturity
  before the index-side workflow exists

## Relationship to follow-on work

This RFC turns the claim design set into an execution order.

Follow-on work should refine:
- concrete issue breakdown for each phase
- validation fixtures and examples for claim artifacts
- the first claim-inspection report shapes in core, CLI, and MCP
