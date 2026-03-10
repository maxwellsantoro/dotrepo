# RFC 0008: Maintainer claim lifecycle

## Status
Draft

## Summary

This RFC defines the first product-level lifecycle for maintainer claims in the
dotrepo index. It turns the existing claim, supersede, and conflict semantics
into a maintainer-controlled workflow without changing the underlying authority
contract.

The lifecycle covers:
- who participates in a maintainer claim
- what states a claim moves through
- what each state means for index operators and downstream consumers
- what audit context must remain visible

This RFC does **not** define authentication integration or final UI.

## Why now

The protocol already defines claim, supersede, precedence, and conflict
visibility. That is enough for consumers to prefer canonical records once they
exist.

What is missing is the product workflow that lets maintainers:
- assert that an overlay describes their project
- request authority handoff in a reviewable way
- move from overlay representation toward canonical in-repo representation
- preserve trust context and historical visibility during that transition

Without a lifecycle, the index would have semantics but no disciplined way to
apply them.

## Non-goals

This RFC does not define:
- external identity or authentication systems
- production UI, website, or API endpoints
- automatic canonical record generation from accepted claims
- silent promotion of an overlay to canonical authority

Canonical precedence still comes from canonical records and canonical mirrors,
not from a claim request by itself.

## Actor roles

### Claimant

The claimant is the party asserting maintainer authority over a repository
representation in the index.

The claimant should provide:
- the repository identity being claimed
- the overlay or draft entry being targeted, if one exists
- the intended maintainer-controlled path forward
- any supporting evidence required by the future workflow

### Reviewer

The reviewer is the index-side human or process responsible for applying the
claim workflow rules.

The reviewer should assess:
- identity alignment
- whether the claim targets the correct overlays or draft entries
- whether the requested outcome matches the authority contract
- whether dispute, rejection, or withdrawal rules apply

Review does not authorize silent field blending from lower-authority overlays
into canonical records.

### Maintainer-controlled canonical source

The maintainer-controlled canonical source is the in-repo `.repo` record, or the
explicit maintainer-controlled step that leads to one.

This role matters because:
- accepted claims should point toward maintainer-controlled canonical authority
- a claim request alone does not become canonical authority
- downstream precedence remains tied to canonical records and canonical mirrors

### Consumers

Consumers are downstream tools, users, or agents that observe the result.

They should be able to tell:
- whether a claim exists
- whether it is pending, accepted, rejected, withdrawn, or disputed
- whether a canonical record now exists
- what overlays remain as superseded or parallel history

## Lifecycle states

The first lifecycle should model these states.

### 1. Draft claim

A draft claim is not yet under active review.

Implications:
- no precedence changes
- no overlay state changes
- the claim is internal or preparatory context only

### 2. Submitted claim

A submitted claim is ready for index-side review.

Implications:
- the targeted repository identity and overlays are explicit
- review can begin
- no authority handoff has happened yet

### 3. In review

An in-review claim is actively being evaluated.

Implications:
- identity matching and workflow correctness are under review
- overlays remain active according to the existing precedence contract
- no canonical promotion happens merely because review has started

### 4. Accepted claim

An accepted claim means the workflow agrees that the claimant is the rightful
maintainer-side authority path for that repository identity.

Implications:
- the accepted claim may trigger or recognize canonical handoff work
- overlays do not become canonical automatically
- if a canonical `.repo` already exists, consumers may complete the handoff using
  the existing precedence rules
- if a canonical `.repo` does not yet exist, the accepted claim should remain
  visible as accepted workflow state, not as canonical authority

### 5. Rejected claim

A rejected claim means the requested authority handoff should not proceed.

Implications:
- no precedence changes
- existing overlays or canonical records stay as they were
- rejection context remains part of the audit trail

### 6. Withdrawn claim

A withdrawn claim is one the claimant has retracted before completion.

Implications:
- no authority handoff occurs from that claim
- the withdrawn state remains visible historically

### 7. Disputed claim

A disputed claim is one where the workflow cannot safely resolve the authority
handoff without further evidence or later product capabilities.

Implications:
- existing precedence rules remain in place
- disagreement stays visible
- the claim history should not be flattened into a success or failure state

## Lifecycle rules

### Claims are identity-scoped

Claims apply only when the repository identity surface matches the existing
authority contract:
- upstream host, owner, and repo path
- any targeted overlay `record.source`
- any corresponding index path
- any canonical mirror path, when present

Claims should not auto-resolve across redirects, mirrors, renames, or fuzzy URL
matches.

### Claims do not authorize field merging

A claim workflow may change which representation is preferred once canonical
authority exists, but it does not authorize field-level blending across records.

If a later canonical record leaves a field missing or intentionally `unknown`,
that absence should remain visible unless a consumer explicitly opts into layered
fallback and preserves provenance.

### Accepted claims and canonical authority are related but distinct

An accepted claim is not itself a canonical record.

The lifecycle should distinguish between:
- workflow acceptance of maintainer authority
- actual presence of a maintainer-controlled canonical `.repo`
- index publication of a canonical mirror

That separation keeps the trust model honest.

### History stays visible

At minimum, claim history should remain inspectable with:
- the lifecycle state
- the repository identity being claimed
- the targeted overlay or draft entries
- review notes or equivalent audit trail
- links to any resulting canonical record or canonical mirror

## Audit expectations

The first maintainer-claim workflow should preserve enough history for later
review, dispute handling, and consumer trust.

That means accepted, rejected, withdrawn, and disputed claims should all remain
traceable rather than being silently collapsed into a final state with no
history.

## Relationship to follow-on work

This RFC defines actor roles and lifecycle stages.

Follow-on design work should refine:
- the index-side claim request record and audit trail
- overlay-to-canonical handoff states
- dispute, rejection, withdrawal, and correction rules
- claim-history visibility in index and machine-facing outputs
- phased implementation planning
