# RFC 0009: Claim request record and audit trail

## Status
Draft

## Summary

This RFC defines the first index-side claim request record shape and audit trail
model for maintainer claims.

The design is intentionally Git-native:
- each claim request lives under the repository identity it targets
- the current claim state is stored in one structured record
- the audit trail is stored as append-only structured events plus optional
  human review notes

This RFC does **not** define authentication integration, website UI, or API
responses. It defines the durable index artifact that later product surfaces
should read and write.

## Why

The claim lifecycle in [`RFC 0008`](./0008-maintainer-claim-lifecycle.md)
defines actors and states, but the index still needs a concrete answer to these
questions:
- where does a claim request live in the tree
- what is the minimum structured data for a claim request
- how do accepted, rejected, withdrawn, and disputed claims stay visible
- how do later tools inspect claim history without mining raw Git commit history

The index should make claim history explicit rather than implicit.

## Non-goals

This RFC does not define:
- external identity proof or login systems
- automatic canonical record generation
- full handoff state semantics for overlays after acceptance
- public index rendering or query API shapes

An accepted claim request is still not canonical authority by itself.

## Proposed Git layout

Claims should live under the same repository identity path as the overlay or
canonical mirror they target.

```text
/repos/
  github.com/
    acme/
      widget/
        record.toml
        evidence.md
        claims/
          2026-03-10-maintainer-claim-01/
            claim.toml
            review.md
            events/
              0001-submitted.toml
              0002-review-started.toml
              0003-accepted.toml
```

This keeps the claim artifact attached to the repository identity rather than
moving it into a separate workflow-only namespace.

## Files and responsibilities

### `claim.toml`

`claim.toml` is the current-state record for the claim.

It should answer:
- what repository identity is being claimed
- who is claiming it, at the workflow level
- what overlays, draft records, or canonical mirrors are targeted
- what the current lifecycle state is
- what the latest known resolution links are

This file is mutable across lifecycle transitions.

### `events/*.toml`

The `events/` directory is the durable structured audit trail.

Each event file should represent one lifecycle transition or one audit-significant
action. Event files should be append-only in normal operation.

That gives downstream tools a stable audit surface without requiring them to
reconstruct state from Git commits alone.

### `review.md`

`review.md` is an optional human-readable note file for review context,
explanations, or dispute detail that does not fit cleanly into structured
fields.

It complements the structured audit trail; it does not replace it.

## Current-state claim record shape

The first record shape should be explicit but narrow.

```toml
schema = "dotrepo-claim/v0"

[claim]
id = "github.com/acme/widget/2026-03-10-maintainer-claim-01"
kind = "maintainer_authority"
state = "submitted"
created_at = "2026-03-10T14:30:00Z"
updated_at = "2026-03-10T14:30:00Z"

[identity]
host = "github.com"
owner = "acme"
repo = "widget"

[claimant]
display_name = "Acme maintainers"
asserted_role = "maintainer"
contact = "maintainers@acme.dev"

[target]
index_paths = [
  "repos/github.com/acme/widget/record.toml",
]
record_sources = [
  "https://github.com/acme/widget",
]
canonical_repo_url = "https://github.com/acme/widget"

[resolution]
canonical_record_path = ".repo"
canonical_mirror_path = "repos/github.com/acme/widget/record.toml"
result_event = "events/0003-accepted.toml"
```

### Required sections

The first design should require:
- `schema`
- `[claim]`
- `[identity]`
- `[claimant]`
- `[target]`

`[resolution]` may be absent until review reaches an outcome that needs it.

## Field semantics

### `[claim]`

- `id`: stable claim identifier within the index
- `kind`: fixed to maintainer authority handoff for the first workflow
- `state`: one of the lifecycle states from RFC 0008
- `created_at`: creation timestamp for the claim record
- `updated_at`: most recent lifecycle or audit-significant update

### `[identity]`

This section repeats the repository identity surface explicitly so tools do not
have to infer it from directory layout alone.

It should match:
- the repository path in the index
- any targeted overlay `record.source`
- any linked canonical mirror or canonical repository URL

### `[claimant]`

This section records the workflow-level claimant identity as presented to the
index workflow.

It is not an external proof system. It is the index's structured statement of
who is asserting the claim.

For the first design, open strings are preferable to hard-coded identity
providers.

### `[target]`

This section records what the claim is trying to affect.

It should include:
- one or more targeted index paths when overlays or draft records already exist
- one or more targeted `record.source` values when relevant
- the canonical repository URL the claimant says they control

This keeps the claim request linked to both index-side and upstream identity
surfaces.

### `[resolution]`

This section records the best-known outcome links after review.

It may include:
- `canonical_record_path`
- `canonical_mirror_path`
- `result_event`
- future fields for rejection or dispute artifacts

The section is descriptive. It does not grant canonical authority by itself.

## Event record shape

Each event file should be individually parseable and append-only in ordinary
workflow use.

```toml
schema = "dotrepo-claim-event/v0"

[event]
sequence = 3
kind = "accepted"
timestamp = "2026-03-12T09:15:00Z"
actor = "index-reviewer"

[transition]
from = "in_review"
to = "accepted"

[summary]
text = "Accepted maintainer authority request after identity alignment review."

[links]
claim = "../claim.toml"
review_notes = "../review.md"
canonical_record_path = ".repo"
```

### Required event fields

The first design should require:
- a stable sequence number within the claim directory
- an event kind
- a timestamp
- an actor label
- a transition block when the event changes lifecycle state
- a short summary

## Minimum audit requirements

At minimum, the audit trail should preserve:
- the submitted claim
- each lifecycle state change
- who or what actor recorded the change
- enough summary text to understand why the change happened
- links to review notes or resulting canonical artifacts when relevant

That means accepted, rejected, withdrawn, and disputed claims remain inspectable
without digging through PR history.

## Why not rely on Git history alone

Git history is necessary, but not sufficient as the primary audit surface.

Git commits alone make it harder for tools and reviewers to answer simple
questions such as:
- what is the current lifecycle state
- what was the last outcome-changing event
- what overlays were targeted
- where is the human review context

The structured claim record plus append-only event files make those questions
answerable directly.

## Visibility rules implied by this design

This RFC does not define final consumer-facing visibility behavior, but it does
imply that later surfaces should be able to expose:
- current claim state from `claim.toml`
- lifecycle history from `events/`
- human review context from `review.md`
- links to superseded overlays and canonical artifacts through the target and
  resolution sections

That work is refined further in follow-on visibility design.

## Relationship to follow-on work

This RFC defines the durable index artifact for claims.

Follow-on work should refine:
- overlay-to-canonical handoff states
- dispute, rejection, withdrawal, and correction rules
- claim-history and superseded-overlay visibility rules
- phased implementation planning

The first handoff-state draft lives in
[`RFC 0010`](./0010-overlay-to-canonical-handoff.md).

Failure-path and correction rules are refined further in
[`RFC 0011`](./0011-claim-failure-and-correction-rules.md).

Claim-history and superseded-overlay visibility rules are refined further in
[`RFC 0012`](./0012-claim-history-and-superseded-overlay-visibility.md).

Phased implementation planning is refined further in
[`RFC 0013`](./0013-phased-maintainer-claim-implementation-plan.md).
