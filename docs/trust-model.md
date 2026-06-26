# Trust model

The trust model is one of dotrepo's core ideas.

A `.repo` record should not imply that all facts are equally authoritative. Instead, dotrepo should communicate where a record came from, how it was derived, and how much confidence downstream consumers should place in it.

In the schema, that means trust metadata belongs to the record itself: `record.status` expresses the authority ladder, and `[record.trust]` carries provenance, confidence, and notes.

Record freshness also stays on the factual record. `record.generated_at` is the
per-record crawl or import timestamp when that metadata is known. It is not a
replacement for `[record.trust]`, and it should not be promoted into a detached
public trust block.

## Record status ladder

- **draft**: an unfinished or speculative record
- **imported**: a record created from existing repo files or platform metadata
- **inferred**: a record containing heuristically or LLM-derived claims
- **reviewed**: a record reviewed by a human contributor or curator
- **verified**: a record whose required fields have been exhaustively resolved
  against evidence through deterministic checks and, where needed,
  candidate-constrained model adjudication; human review is not implied
- **canonical**: a maintainer-controlled in-repo record treated as authoritative for the project

## Provenance categories

- **declared**: stated directly by project maintainers or canonical records
- **imported**: parsed from source materials such as README, CODEOWNERS, or platform metadata
- **inferred**: derived from heuristics, code inspection, or LLM interpretation
- **verified**: confirmed against evidence through deterministic verification,
  constrained adjudication with post-checks, human review, or explicit
  maintainer validation

These are the reference provenance values for v0.1, not a closed enum. Tools should preserve unknown provenance strings even if they only interpret the reference vocabulary directly.

Likewise, `record.trust.confidence` uses a reference vocabulary of `low`, `medium`, and `high` in v0.1, but remains an open string so the protocol can evolve without forcing an immediate schema break.

## Trust implications

- Agents and tools should prefer canonical records when available.
- Imported and inferred overlays are useful, but should be consumed with awareness of their status.
- Consumers that specifically require human review should check for `reviewed`
  status or provenance instead of treating `verified` as a synonym for human
  approval.
- Conflicts between sources should surface explicitly rather than being quietly flattened.
- Claim and supersede are authority handoff semantics, not a requirement for a full
  productized maintainer workflow before precedence can be defined.
- When a canonical record and an overlay disagree for the same repository identity,
  consumers should prefer the canonical value by default and preserve the overlay's
  conflicting claim as visible trust context.

## Authority handoff implications

- Claim and supersede are identity-level operations. They only apply when the
  repository identity surface matches across the canonical upstream path, any overlay
  `record.source`, and any corresponding index path.
- The default precedence ladder is: canonical `.repo`, canonical mirror, verified
  overlay, reviewed overlay, imported overlay, inferred overlay, then draft.
- Precedence chooses a default record; it does not authorize silent field-level
  blending across records.
- A missing or intentionally `unknown` field in a higher-authority record should stay
  missing or `unknown` by default unless a consumer explicitly opts into layered
  fallback and preserves provenance.

## Selection tie-breaking

When two or more candidate records share the same precedence rank, dotrepo breaks
ties in this order:

1. **Accepted maintainer claim** attached to the candidate record
2. **In-review maintainer claim** attached to the candidate record
3. **Lexicographic `manifest_path`** for stable, deterministic ordering

Claim context enriches the selected record in `query` and `trust` responses, but
only advances selection when ranks are otherwise equal. A higher-status overlay
still wins over a lower-status native record even when the native record has an
accepted claim in flight.

See [`RFC 0004`](../rfcs/0004-index-and-trust-model.md) and the worked examples in
[`authority-handoff-examples.md`](./authority-handoff-examples.md) for the normative
contract and reference scenarios.

For the autonomous promotion rules that can mint `verified` overlays, see
[`factual-crawl-automation.md`](./factual-crawl-automation.md) and
[`ROADMAP.md`](../ROADMAP.md).
