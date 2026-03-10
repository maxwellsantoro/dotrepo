# RFC 0011: Claim failure and correction rules

## Status
Draft

## Summary

This RFC defines the rules for disputed, rejected, withdrawn, and corrected
maintainer claims.

The goal is simple:
- unsuccessful or incomplete claims must remain visible as part of the trust
  story
- later corrections must amend prior outcomes without erasing them
- reviewers should have explicit guidance for how each outcome affects claim
  state, handoff state, and audit history

This RFC complements the lifecycle, claim-record, and handoff-state drafts. It
does not replace them.

## Why

The maintainer-claim workflow is only trustworthy if it handles failure and
revision explicitly.

Without explicit rules, future tools or reviewers would be tempted to:
- collapse a rejected claim into non-existence
- treat a withdrawal as if the claim had never been filed
- silently “fix” an accepted claim by overwriting history
- flatten an unresolved dispute into a clean handoff

That would damage the core trust model, which depends on keeping provenance and
review history visible.

## Non-goals

This RFC does not define:
- abuse-prevention policy
- identity proof systems
- moderation staffing or escalation staffing
- API or UI presentation details

## Outcome categories

The workflow should treat these as distinct outcome categories:

1. `rejected`
2. `withdrawn`
3. `disputed`
4. `corrected`

These categories apply to claim workflow history. They do not replace record
`status`, and they do not by themselves grant canonical authority.

## Rejected claims

A rejected claim is one the reviewer or workflow decides should not proceed.

Typical reasons:
- identity mismatch
- insufficient review evidence
- incorrect target overlays
- the claimant is not accepted as the maintainer-side authority path

Rules:
- the claim record state becomes `rejected`
- no overlay handoff is completed from that claim
- targeted overlays remain as they were before the claim
- the rejection reason should be summarized in structured event history and may
  be elaborated in `review.md`

Implications:
- rejection is an explicit historical result, not deletion
- a later new claim may still be filed for the same repository identity

## Withdrawn claims

A withdrawn claim is one the claimant retracts before the workflow completes.

Typical reasons:
- claimant filed too early
- claimant targeted the wrong overlays
- claimant decided to wait until canonical `.repo` adoption is ready

Rules:
- the claim record state becomes `withdrawn`
- no overlay handoff is completed from that claim
- prior submitted or in-review events remain part of the audit trail
- the withdrawal should include a timestamp and actor label like any other event

Implications:
- withdrawal is not rejection
- withdrawal should not imply reviewer disapproval unless the audit trail says so

## Disputed claims

A disputed claim is one where the workflow cannot safely resolve the authority
handoff into an accepted or rejected result with current evidence.

Typical reasons:
- competing assertions of maintainer authority
- unresolved repository identity disagreement
- disagreement about whether the targeted overlay belongs in the handoff scope
- disagreement about the canonical source path or resulting mirror link

Rules:
- the claim record state becomes `disputed`
- the audit trail should capture enough summary context to explain the dispute
- targeted overlays should remain `parallel`, `pending_canonical`, or otherwise
  unresolved rather than being silently marked `superseded`
- downstream consumers should be able to tell that disagreement remains open

Implications:
- dispute is not a soft acceptance
- dispute is not a hidden internal note
- future evidence or workflow steps may still resolve the claim later

## Corrected claims

A corrected claim is a claim whose earlier accepted, rejected, withdrawn, or
disputed state needs amendment without erasing the earlier outcome.

Typical reasons:
- the targeted overlay set was incomplete or wrong
- a review note or resolution link was incorrect
- the handoff outcome was recorded incorrectly
- later evidence requires adjusting the prior result

Rules:
- correction should be represented as one or more new events, not by deleting
  prior events
- `claim.toml` may be updated to reflect the latest corrected current state
- the audit trail should preserve both the earlier outcome and the correcting
  event
- when correction changes overlay handoff outcome, that new handoff state should
  be recorded explicitly

Implications:
- correction is amendment, not erasure
- accepted claims may be corrected without pretending the earlier acceptance
  never happened
- rejected or disputed claims may also be corrected when later evidence justifies
  it

## Event expectations

The claim audit trail should support at least these event kinds:
- `submitted`
- `review_started`
- `accepted`
- `rejected`
- `withdrawn`
- `disputed`
- `corrected`

`corrected` events should include enough links or summary text to identify what
prior outcome they are amending.

## What must remain visible

For rejected, withdrawn, disputed, and corrected claims, later surfaces should
be able to preserve:
- current claim state
- prior outcome-changing events
- actor labels and timestamps
- short reason summaries
- links to affected overlays or canonical artifacts when relevant

That visibility requirement applies even when the current state later becomes a
clean acceptance or handoff.

## Reviewer guidance

### When to reject

Reject when the workflow has enough information to conclude the claim should not
proceed.

### When to mark disputed

Mark disputed when the workflow does not have a safe, final answer and the
remaining disagreement is substantive.

### When to record withdrawal

Record withdrawal when the claimant retracts the request, even if the reviewer
believes the claim would otherwise have succeeded or failed.

### When to use correction

Use correction when the workflow needs to amend prior recorded history while
preserving that history.

Do not use correction as a quiet rewrite of the audit trail.

## Relationship to handoff states

These rules interact with handoff states this way:
- rejected claims should not create `superseded` handoff outcomes
- withdrawn claims should not create `superseded` handoff outcomes
- disputed claims should leave targeted overlays unresolved rather than silently
  superseding them
- corrected claims may revise a handoff state, but only through explicit new
  audit events

## Relationship to follow-on work

This RFC defines failure-path and correction rules.

Follow-on work should refine:
- claim-history and superseded-overlay visibility rules
- phased implementation planning

Claim-history and superseded-overlay visibility rules are refined further in
[`RFC 0012`](./0012-claim-history-and-superseded-overlay-visibility.md).

Phased implementation planning is refined further in
[`RFC 0013`](./0013-phased-maintainer-claim-implementation-plan.md).
