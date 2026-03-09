# RFC 0004: Index and trust model

## Status
Draft

## Summary

The dotrepo index is a Git-backed, PR-driven collection of repository records. It is both a practical contribution surface and the connective layer that makes the protocol useful across the ecosystem.

## Why the index exists

The index lets any public repository become mechanically visible even before maintainers adopt dotrepo.

That supports:
- discovery by users
- orientation by agents and tools
- later claiming and verification by maintainers

## Record types

- **overlay record**: external representation of a public repository
- **canonical mirror**: index representation corresponding to a canonical in-repo record
- **draft record**: early or incomplete contribution under review

## Suggested Git repo layout

```text
/repos/
  github.com/
    BurntSushi/
      ripgrep/
        record.toml
        evidence.md
```

`record.toml` stores the structured metadata.
`evidence.md` stores explanatory notes, citations, and review context when needed.

Host, owner, and repository path segments should match the canonical upstream origin exactly. Index paths are part of the record identity surface, so path drift should be treated as a correctness issue rather than a cosmetic detail.

For the v0.1 seed index, CI should also require:
- a sibling `evidence.md` for every `record.toml`
- `record.mode = "overlay"`
- `record.source` to resolve to the same `<host>/<owner>/<repo>` identity as the index path
- `repo.homepage`, when it is also a repository URL, to match that same identity

Seed-index CI should also lint for contribution quality without making the core protocol artificially rigid. Day-one warnings should cover:
- non-reference `record.trust.confidence` vocabulary
- non-reference `record.trust.provenance` vocabulary
- evidence that does not explain imported or inferred claims clearly
- evidence that does not explain where build and test commands came from
- unexplained `unknown` placeholders for fields like security contacts

## Contribution workflow

1. A contributor or agent proposes a record.
2. CI validates schema, identity alignment, and required evidence files.
3. CI and review checks ensure the record distinguishes declared, imported, and inferred claims, and that evidence is specific enough for future maintainers to trust the overlay.
4. Approved records merge.
5. Maintainers may later claim or supersede a record with a canonical in-repo `.repo`.

## Claim and supersede semantics

The seed index needs authority handoff semantics before it needs a productized
claim workflow.

For v0.1 and the near-term roadmap:
- **claim** means a maintainer-controlled canonical `.repo` record asserts that it
  represents the same repository identity as an existing overlay or draft index entry
- **supersede** means that a higher-authority record becomes the default record for
  that repository identity without erasing the older overlay's history or evidence
- **canonical mirror** means an index entry derived from a maintainer-controlled
  canonical `.repo`; it carries canonical authority for index consumers, but does not
  outrank the source `.repo` itself

### Repository identity matching

Claim and supersede are identity-level operations. They should only apply when the
repository identity surface matches across every available surface:
- the canonical upstream host, owner, and repo path
- the record's `record.source`
- the index path used by any corresponding overlay or canonical mirror
- `repo.homepage`, when it is also a repository URL for the same repository

Consumers should not auto-claim across redirects, mirrors, renamed repositories, or
partial matches. Those cases need explicit human review or a future maintainer-claim
workflow; they are not safe to infer from URL similarity alone.

### Precedence ladder

When multiple records describe the same repository identity, consumers should choose a
default record using this precedence order:

1. maintainer-controlled canonical `.repo`
2. canonical mirror derived from that `.repo`
3. verified overlay
4. reviewed overlay
5. imported overlay
6. inferred overlay
7. draft record

Within the same precedence level, consumers should not synthesize or silently resolve
the disagreement. Equal-authority records remain parallel claims until a maintainer,
reviewer, or future workflow makes the relationship explicit.

Precedence is a record-selection rule for default presentation. It is not permission to
blend fields across records. A missing or intentionally `unknown` field in a
higher-authority record should remain missing or `unknown` by default. Consumers should
not silently backfill it from lower-authority records unless they explicitly opt into a
layered fallback mode and preserve the lower-authority provenance as visible context.

### What claim means

Claim has these contract implications:
- the canonical record becomes the preferred representation for that repository identity
- the claim may target one overlay, several overlays, or a draft entry, as long as the
  identity surface matches
- claim does not import overlay facts into the canonical record automatically
- claim does not erase overlay evidence, review notes, or provenance

### What supersede means

Supersede has these contract implications:
- the higher-authority record becomes the default record for that repository identity
- superseded records remain queryable and inspectable as historical evidence,
  third-party curation, or pre-adoption records
- overlay status alone does not imply that the superseded record was malicious or even
  incorrect; it only means a stronger authority is now available
- when no canonical record exists, a higher-status overlay may supersede a lower-status
  overlay for default presentation
- equal-status overlays do not supersede each other automatically

At minimum, superseded records should remain inspectable with:
- `record.mode`
- `record.status`
- `record.source`
- `record.trust`
- the index path or equivalent locator
- the evidence location or equivalent review trail when one exists

The contract implication is simple:
- when a maintainer-controlled canonical record exists for the same identity, consumers
  should prefer it by default over imported or inferred overlays
- overlays remain useful as historical evidence, third-party curation, or pre-adoption
  records, but they should not continue to masquerade as the best available authority
- a future maintainer claim workflow may automate this handoff, but the precedence rule
  does not depend on that workflow existing yet

## Conflict surfacing rules

The protocol should not silently flatten disagreement once multiple records exist for
the same repository identity.

Consumers should treat conflicts this way:
- if a canonical record and an overlay disagree, prefer the canonical value by default
  while preserving the conflicting overlay claim as visible context
- if multiple overlays disagree and no canonical record exists, do not merge them into a
  synthetic fact without surfacing the disagreement and each record's trust metadata
- if a field remains `unknown` intentionally, treat that as an explicit absence of
  authority, not as a conflict by itself

At minimum, conflict surfacing should preserve:
- `record.mode`
- `record.status`
- `record.source`
- `record.trust`
- the reason one record was preferred over another
- the index path or equivalent locator for each conflicting record
- the evidence location or equivalent review trail when one exists

That makes it possible for downstream tools to say not only *what* conflicts, but
also *why* one record is preferred and what kind of evidence supports the other.

Worked examples for these rules live in
[`docs/authority-handoff-examples.md`](../docs/authority-handoff-examples.md).

## Trust surfacing

The index must make status and provenance obvious, not hidden in metadata.

Users and agents should be able to tell immediately whether a record is inferred, reviewed, verified, or canonical.

Trust metadata belongs to the record itself and should live under `[record.trust]`, not as a detached sibling section.

## Known horizon

A GitHub repository is the right day-one collaboration surface, but it may not remain the only distribution mechanism as the index grows. The protocol should not assume that Git is the final serving layer.
