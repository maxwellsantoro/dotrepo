# Import fixture rationale

The canonical importer regression barrier is executable:

- fixtures: `crates/dotrepo-core/tests/fixtures/import/`
- expectations: `crates/dotrepo-core/tests/fixtures/import/expectations.json`
- gate: `crates/dotrepo-core/tests/import_quality_gate.rs`

This document records why the fixture families exist. It intentionally does not
copy expected values or pass counts from the machine-readable expectations.

## Contract

- Native imports land as `record.status = "draft"`.
- Overlay imports land as `imported` when no fields are inferred and `inferred`
  otherwise.
- Overlay imports emit `evidence.md`; native imports do not.
- README heuristics may extract title, description, and documentation entry
  points, but must not invent canonical data.
- `CODEOWNERS` and `SECURITY.md` remain bootstrap evidence, not
  maintainer-verified truth.

## Fixture families

README fixtures cover:

- badges and images before useful prose
- setext and HTML headings
- inline HTML wrappers
- documentation navigation and explicit documentation labels
- descriptions without explicit project titles

Ownership fixtures cover:

- conventional and root-level `CODEOWNERS`
- repository-wide ownership with narrower overrides
- genuinely ambiguous multi-team ownership

Security fixtures cover:

- policy and reporting URLs
- inline, reference-style, and HTML `mailto:` links
- `mailto:` query parameters
- policy files with no parseable contact

The fallback fixture contains no conventional import surfaces.

## Intentional incompleteness

- A missing explicit project title may require an inferred repository name.
- A README without useful descriptive prose may require an inferred
  description.
- A security policy without a parseable mailbox or URL remains `unknown`.
- Broad multi-team ownership leaves `owners.team` unset.
- A repository without conventional surfaces keeps inferred bootstrap values.

These are successful abstentions, not failures to be filled at any cost.

## Changing importer behavior

An importer change should update fixtures and `expectations.json` in the same
patch. The pull request should state whether it adds coverage, changes behavior,
or both. Intentionally incomplete cases must remain visible in expectations.

Run:

```bash
cargo test -p dotrepo-core --test import_quality_gate
```
