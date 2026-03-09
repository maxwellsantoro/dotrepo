# Trust model

The trust model is one of dotrepo's core ideas.

A `.repo` record should not imply that all facts are equally authoritative. Instead, dotrepo should communicate where a record came from, how it was derived, and how much confidence downstream consumers should place in it.

In the schema, that means trust metadata belongs to the record itself: `record.status` expresses the authority ladder, and `[record.trust]` carries provenance, confidence, and notes.

## Record status ladder

- **draft**: an unfinished or speculative record
- **imported**: a record created from existing repo files or platform metadata
- **inferred**: a record containing heuristically or LLM-derived claims
- **reviewed**: a record reviewed by a human contributor or curator
- **verified**: a record checked against evidence to a higher standard
- **canonical**: a maintainer-controlled in-repo record treated as authoritative for the project

## Provenance categories

- **declared**: stated directly by project maintainers or canonical records
- **imported**: parsed from source materials such as README, CODEOWNERS, or platform metadata
- **inferred**: derived from heuristics, code inspection, or LLM interpretation
- **verified**: confirmed through human review or explicit maintainer validation

These are the reference provenance values for v0.1, not a closed enum. Tools should preserve unknown provenance strings even if they only interpret the reference vocabulary directly.

Likewise, `record.trust.confidence` uses a reference vocabulary of `low`, `medium`, and `high` in v0.1, but remains an open string so the protocol can evolve without forcing an immediate schema break.

## Trust implications

- Agents and tools should prefer canonical records when available.
- Imported and inferred overlays are useful, but should be consumed with awareness of their status.
- Conflicts between sources should surface explicitly rather than being quietly flattened.
