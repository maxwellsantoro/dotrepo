# RFC 0010: Overlay-to-canonical handoff states

## Status
Draft

## Summary

This RFC defines the handoff states and review outcomes that connect maintainer
claim workflow to canonical authority.

The core distinction is:
- a claim workflow may be accepted before canonical authority is actually present
- canonical authority becomes preferred only when a maintainer-controlled
  canonical `.repo` exists for the same repository identity
- targeted overlays then move into explicit handoff outcomes such as
  `superseded`, `parallel`, or `disputed`

This RFC does not change the precedence ladder. It defines how index operators
and future product surfaces should describe the transition from overlay-backed
representation to canonical-backed representation.

## Why

The current contract already says:
- canonical records win by default when identity matches
- overlays remain visible as trust context and historical evidence
- accepted claims are not themselves canonical authority

What is still missing is the explicit handoff layer between those rules:
- when is a claim merely accepted but still waiting on canonical authority
- when is an overlay actually superseded
- when should an overlay remain parallel instead of being treated as superseded
- how should unresolved disagreement be described

Without these states, reviewers and future tools would have to infer too much
from claim acceptance alone.

## Non-goals

This RFC does not define:
- query or API payload changes
- UI or public site presentation
- authentication or identity proof
- bundle or workspace semantics

## Handoff review outcomes

For a claim that targets one or more overlays or draft records, review should
produce one of these high-level outcomes for each targeted record:

1. `pending_canonical`
2. `superseded`
3. `parallel`
4. `rejected`
5. `withdrawn`
6. `disputed`

These are handoff outcomes, not replacements for record `status`.

## Handoff state meanings

### `pending_canonical`

The claim workflow has accepted the maintainer authority path, but canonical
authority is not yet available for default selection.

Typical cases:
- the claim has been accepted, but the canonical `.repo` does not yet exist
- the canonical `.repo` exists privately but is not yet available to the index
- the canonical mirror link is not yet complete enough for index-side handoff

Implications:
- the targeted overlay remains the best available public representation
- no overlay is marked superseded yet
- downstream consumers should not treat accepted claim state itself as canonical

### `superseded`

The targeted overlay has been cleanly displaced as the default representation by
a maintainer-controlled canonical `.repo` or its canonical mirror.

Required conditions:
- repository identity matches under the existing claim/supersede rules
- canonical authority exists
- the handoff links are explicit enough to point from the overlay to the
  resulting canonical record or canonical mirror

Implications:
- canonical representation wins by default
- the overlay remains inspectable as history, curation, and trust context
- the overlay should not continue to masquerade as the best available authority

### `parallel`

The targeted overlay remains a visible parallel claim rather than being marked
superseded.

Typical cases:
- review concludes the overlay was not actually the same repository identity
- the overlay remains relevant as a distinct representation outside the claim
  scope
- disagreement exists that should remain explicit instead of being collapsed into
  a clean handoff

Implications:
- the overlay is still visible as an active parallel representation
- the handoff did not complete for that overlay
- reviewers should explain why the overlay remained parallel instead of becoming
  superseded

### `rejected`

The requested handoff should not proceed for the targeted overlay.

Implications:
- no canonical handoff occurs through this claim
- the existing overlay or canonical situation remains unchanged
- the rejection reason should remain auditable

### `withdrawn`

The claimant retracted the handoff request before completion.

Implications:
- no handoff occurs through this claim
- withdrawal should remain visible in the audit trail

### `disputed`

The targeted overlay is part of a claim that could not safely resolve into a
clean handoff.

Typical cases:
- unresolved disagreement about maintainer authority
- unresolved disagreement about repository identity matching
- unresolved disagreement about whether a canonical source is in scope

Implications:
- no clean supersede decision should be recorded for that overlay
- disagreement should remain explicit
- future workflow or evidence may resolve it later

## When handoff is complete

A canonical handoff should be considered complete only when all of the following
are true:

1. the claim workflow reached an outcome that permits handoff
2. a maintainer-controlled canonical `.repo` exists for the same repository
   identity
3. the identity match is explicit under the existing contract
4. the targeted overlay is linked to the resulting canonical record or canonical
   mirror through the claim record or audit trail
5. reviewers have recorded whether the overlay outcome is `superseded` or
   `parallel`

Claim acceptance alone is not handoff completion.

## Default rules for canonical-over-overlay transitions

### Clean handoff rule

If canonical authority exists and identity matches, the default overlay outcome
should be `superseded` unless reviewers have a specific reason to preserve that
overlay as `parallel`.

### No silent parallel rule

If an overlay remains `parallel`, the audit trail should say why. Parallel is
not the silent default for an otherwise clean canonical handoff.

### No silent supersede rule

If canonical authority does not yet exist, the overlay should remain
`pending_canonical` rather than being marked `superseded` early.

### Equal-authority disagreement rule

If the workflow cannot safely collapse disagreement into a clean handoff, the
result should remain `parallel` or `disputed`, not an implied supersede.

## Worked scenarios

### 1. Accepted claim, canonical not published yet

Outcome:
- claim lifecycle may be `accepted`
- targeted overlay handoff state is `pending_canonical`
- overlay remains the best available public representation

### 2. Canonical `.repo` merged, clean identity match

Outcome:
- claim lifecycle may remain `accepted`
- targeted overlay handoff state becomes `superseded`
- canonical `.repo` and canonical mirror become the default representation

### 3. Canonical exists, but targeted overlay is not actually the same identity

Outcome:
- claim may still be accepted for the maintainer identity path
- that specific overlay remains `parallel`
- audit trail should explain the mismatch clearly

### 4. Review cannot resolve authority disagreement

Outcome:
- targeted overlay is `disputed`
- no clean handoff is recorded
- existing trust and conflict context remain visible

## Relationship to claim record and audit trail

The claim request record should be able to capture:
- current claim lifecycle state
- targeted overlays and canonical links
- current overlay handoff outcomes

The audit trail should capture:
- when a targeted overlay moved to `pending_canonical`
- when it later moved to `superseded` or remained `parallel`
- why a disputed or rejected outcome was recorded

## Relationship to follow-on work

This RFC defines handoff outcomes and completion conditions.

Follow-on work should refine:
- dispute, rejection, withdrawal, and correction rules
- claim-history visibility in machine-facing outputs
- phased implementation planning

Failure-path and correction rules are refined further in
[`RFC 0011`](./0011-claim-failure-and-correction-rules.md).

Claim-history and superseded-overlay visibility rules are refined further in
[`RFC 0012`](./0012-claim-history-and-superseded-overlay-visibility.md).

Phased implementation planning is refined further in
[`RFC 0013`](./0013-phased-maintainer-claim-implementation-plan.md).
