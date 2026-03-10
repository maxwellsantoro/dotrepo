# RFC 0012: Claim-history and superseded-overlay visibility

## Status
Draft

## Summary

This RFC defines how claim history and superseded overlays should remain visible
across index artifacts, future claim-inspection surfaces, and conflict-aware
query or trust outputs.

The core rule is simple:
- claim workflow history should remain inspectable without mining raw Git history
- superseded overlays should remain visible as historical and trust-bearing
  records
- claim-aware visibility should extend the existing `selection` / `conflicts`
  model rather than inventing a separate authority story

This RFC does not define final website layout or final CLI/API command names. It
defines the visibility contract that later surfaces should preserve.

## Why

The preceding claim RFCs define:
- lifecycle states
- durable claim and event records
- handoff outcomes
- rejection, withdrawal, dispute, and correction rules

What remains is the consumer-facing visibility rule.

Without that rule, later tooling would be tempted to:
- hide accepted claims once canonical authority exists
- drop superseded overlays from ordinary inspection
- bury rejected or withdrawn claims in Git history only
- expose claim workflow through a separate model that does not line up with
  `selection` / `conflicts`

That would weaken the trust model precisely when maintainer handoff begins to
matter.

## Non-goals

This RFC does not define:
- final public site information architecture
- search ranking or discovery UX
- authentication or identity proof
- full query/API implementation
- record-level field merging across authority boundaries

## Visibility layers

Claim visibility should be preserved across three layers.

### 1. Index artifact layer

The index tree should retain the durable claim artifacts defined in
[`RFC 0009`](./0009-claim-request-and-audit-trail.md):
- `claim.toml`
- append-only `events/*.toml`
- optional `review.md`

The index tree should also retain targeted overlays after handoff.

That means:
- a clean handoff should not delete or relocate the superseded overlay into an
  opaque archive
- claim state should remain inspectable from the repository identity path
- superseded overlays should still have stable locators, evidence files, and
  source/trust metadata

Git history remains useful, but it should not be the only place consumers can
discover what happened.

### 2. Record-selection layer

Conflict-aware query and trust surfaces already expose:
- `selection`
- `conflicts`
- stable selection reasons
- `superseded` and `parallel` relationships

Claim-aware visibility should extend that model rather than replace it.

That means:
- `selection.reason` and `conflicts[].relationship` remain the primary
  explanation of which record won
- claim context may be added to record summaries when it materially explains the
  record's current visibility
- claim history should not require a second precedence model outside
  `selection` / `conflicts`

### 3. Claim-inspection layer

Later claim-aware surfaces should provide a dedicated inspection path for full
claim history.

That surface should answer:
- what claim exists for this repository identity
- what the current claim state is
- what overlays or draft records were targeted
- what the current handoff outcome is for each target
- what events produced the current state

This layer is where rejected, withdrawn, and corrected history can be inspected
in full without cluttering every ordinary query response.

## Minimum visibility contract

At minimum, a claim-aware implementation should preserve:
- claim identifier
- current claim state
- latest outcome-changing event kind and timestamp
- claim record locator
- review note locator when one exists
- targeted overlay or draft locators
- per-target handoff outcome (`pending_canonical`, `superseded`, `parallel`,
  `rejected`, `withdrawn`, or `disputed`)
- canonical record or canonical mirror locator when one exists

That minimum contract applies even after a clean canonical handoff.

## Superseded-overlay rules

### Superseded overlays remain ordinary inspectable records

A superseded overlay should remain inspectable with at least:
- `record.mode`
- `record.status`
- `record.source`
- `record.trust`
- its manifest or index path
- its evidence location when one exists

This is consistent with the existing trust model in
[`RFC 0004`](./0004-index-and-trust-model.md).

### Superseded does not mean hidden

When a canonical record wins by default, the superseded overlay should still be
discoverable through at least one of:
- the repository identity path in the index
- a conflict-aware trust or query response
- a dedicated claim-inspection surface

Consumers should not have to mine Git history to find the displaced overlay.

### Superseded does not imply wrongdoing

Visibility language should preserve the existing meaning of supersede:
- the overlay is no longer the preferred authority
- the overlay may still be accurate, useful, and reviewable
- the overlay remains part of the provenance story

## State-specific visibility rules

### Accepted claim with `pending_canonical`

If a claim is accepted but canonical authority is not yet available:
- the current overlay remains the best available public representation
- ordinary trust or query inspection may surface accepted claim context on that
  selected overlay
- no target overlay should be shown as `superseded` yet

### Accepted claim with completed supersede

If canonical authority exists and the handoff is complete:
- the canonical record remains the selected default
- targeted overlays remain visible as `conflicts[].relationship = "superseded"`
- claim context should remain available on the superseded overlay record summary
  or through dedicated claim inspection

### Parallel or disputed outcome

If a target remains `parallel` or the claim is `disputed`:
- ordinary trust or query output should continue surfacing the disagreement
  through the existing `parallel` relationship or unresolved competing records
- claim context should indicate that the disagreement is workflow-visible, not a
  silent implementation detail

### Rejected or withdrawn outcome

Rejected and withdrawn claims should remain visible through claim-inspection
surfaces and index artifacts.

Ordinary trust or query surfaces do not need to repeat rejected or withdrawn
history on every response when that history does not affect current selection.
However, later claim-aware inspection for the repository identity should still
make those outcomes visible.

### Corrected outcome

Correction should behave as an amendment rule:
- ordinary trust or query surfaces should present the current effective state
- claim-inspection surfaces should still preserve the earlier amended outcome and
  the correcting event

## Recommended machine-facing shape

This RFC does not require immediate CLI or API changes, but later machine-facing
surfaces should preserve compatibility with the existing record-selection model.

For conflict-aware record summaries, the recommended extension is an optional
claim block nested under the record summary:

```json
{
  "record": {
    "manifestPath": "/index/repos/github.com/acme/widget/record.toml",
    "record": {
      "mode": "overlay",
      "status": "reviewed",
      "source": "https://github.com/acme/widget"
    },
    "claim": {
      "id": "github.com/acme/widget/2026-03-10-maintainer-claim-01",
      "state": "accepted",
      "handoff": "superseded",
      "claimPath": "/index/repos/github.com/acme/widget/claims/2026-03-10-maintainer-claim-01/claim.toml",
      "latestEvent": "/index/repos/github.com/acme/widget/claims/2026-03-10-maintainer-claim-01/events/0004-superseded.toml",
      "reviewPath": "/index/repos/github.com/acme/widget/claims/2026-03-10-maintainer-claim-01/review.md"
    }
  }
}
```

Recommended properties:
- `id`
- `state`
- `handoff`
- `claimPath`
- `latestEvent`
- `reviewPath` when present

This keeps claim context attached to the record whose visibility it explains.

### Dedicated claim-inspection shape

Later claim-aware inspection surfaces should expose the full ledger more directly
through a claim-centric shape such as:

```json
{
  "claim": {
    "id": "github.com/acme/widget/2026-03-10-maintainer-claim-01",
    "state": "accepted",
    "claimPath": "/index/repos/github.com/acme/widget/claims/2026-03-10-maintainer-claim-01/claim.toml",
    "reviewPath": "/index/repos/github.com/acme/widget/claims/2026-03-10-maintainer-claim-01/review.md"
  },
  "targets": [
    {
      "path": "/index/repos/github.com/acme/widget/record.toml",
      "handoff": "superseded",
      "canonicalMirrorPath": "/index/repos/github.com/acme/widget/record.toml"
    }
  ],
  "events": [
    {
      "kind": "submitted",
      "timestamp": "2026-03-10T14:30:00Z"
    },
    {
      "kind": "accepted",
      "timestamp": "2026-03-12T09:15:00Z"
    }
  ]
}
```

The exact command or API surface can vary later. The visibility content should
not.

## Worked examples

### 1. Accepted claim, canonical not published yet

Expected visibility:
- ordinary trust output may still select the overlay as the only matching record
- the selected overlay may expose `claim.state = "accepted"` and
  `claim.handoff = "pending_canonical"`
- dedicated claim inspection shows the accepted state and the latest events

### 2. Clean canonical handoff

Expected visibility:
- trust or query selects the canonical record
- the former overlay remains visible under `conflicts[]` with
  `relationship = "superseded"`
- the superseded overlay remains inspectable by index path, with claim context
  linking it to the accepted handoff

### 3. Disputed claim with unresolved overlay disagreement

Expected visibility:
- ordinary trust output continues surfacing the disagreement through `parallel`
  or unresolved competing records
- claim inspection shows `state = "disputed"` plus the relevant event history
- no record is silently presented as cleanly superseded

### 4. Rejected claim after review

Expected visibility:
- ordinary trust and query behavior remain unchanged if selection is unaffected
- claim inspection still shows the rejected claim, the targeted overlays, and the
  rejection event
- reviewers can inspect the history without searching commit logs

## Compatibility rule

Claim-history visibility should complement, not replace, the existing trust and
selection model.

In practical terms:
- use `selection` / `conflicts` to explain current preferred records
- use claim context to explain why a record is pending, superseded, parallel, or
  disputed in workflow terms
- use dedicated claim inspection to expose full rejected, withdrawn, and
  corrected history

That keeps ordinary record selection compact while preserving the full audit
story when it matters.

## Relationship to follow-on work

This RFC defines the visibility contract.

Follow-on work should refine:
- concrete CLI and MCP claim-inspection commands
- public API or site rendering of claim history
- how claim-aware visibility is phased into index validation and review tooling

Phased implementation planning is refined further in
[`RFC 0013`](./0013-phased-maintainer-claim-implementation-plan.md).
