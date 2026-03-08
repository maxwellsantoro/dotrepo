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

## Contribution workflow

1. A contributor or agent proposes a record.
2. CI validates schema, trust fields, and required provenance metadata.
3. Review checks ensure the record distinguishes declared, imported, and inferred claims.
4. Approved records merge.
5. Maintainers may later claim or supersede a record with a canonical in-repo `.repo`.

## Trust surfacing

The index must make status and provenance obvious, not hidden in metadata.

Users and agents should be able to tell immediately whether a record is inferred, reviewed, verified, or canonical.

Trust metadata belongs to the record itself and should live under `[record.trust]`, not as a detached sibling section.

## Known horizon

A GitHub repository is the right day-one collaboration surface, but it may not remain the only distribution mechanism as the index grows. The protocol should not assume that Git is the final serving layer.
