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

Claim and supersede are identity-level operations. They should only apply when the
repository identity surface matches:
- the canonical upstream host, owner, and repo path
- the record's `record.source`
- the index path used by any corresponding overlay or canonical mirror

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

That makes it possible for downstream tools to say not only *what* conflicts, but
also *why* one record is preferred and what kind of evidence supports the other.

## Trust surfacing

The index must make status and provenance obvious, not hidden in metadata.

Users and agents should be able to tell immediately whether a record is inferred, reviewed, verified, or canonical.

Trust metadata belongs to the record itself and should live under `[record.trust]`, not as a detached sibling section.

## Known horizon

A GitHub repository is the right day-one collaboration surface, but it may not remain the only distribution mechanism as the index grows. The protocol should not assume that Git is the final serving layer.
