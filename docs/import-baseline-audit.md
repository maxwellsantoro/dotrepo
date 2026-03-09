# Import baseline audit

This began as the issue `#1` baseline for the reusable import fixture pack at
`crates/dotrepo-core/tests/fixtures/import/`.

The goal is to make current importer behavior concrete before issue `#2`
and issue `#3` improve heuristics. This document is intentionally descriptive,
not normative: it records what the importer does today so later work can show
 what got better on a fixed set of inputs.

Issue `#4` adds a machine-readable expectation snapshot at
`crates/dotrepo-core/tests/fixtures/import/expectations.json` and a regression
test at `crates/dotrepo-core/tests/import_quality_gate.rs`. That snapshot is
the enforced CI gate for the current fixture set, including the README-focused
cases added in issue `#2` and the owner/security cases added in issue `#3`.

Common current behavior:
- Native imports always land as `record.status = "draft"`.
- Overlay imports land as `record.status = "imported"` when `inferred_fields` is empty and `record.status = "inferred"` otherwise.
- Overlay imports always emit `evidence.md`; native imports do not.

## `full-signals`

Surfaces present:
- `README.md`
- `.github/CODEOWNERS`
- `.github/SECURITY.md`

Current import summary:
- `repo.name = "Orbit"`
- `repo.description = "Fast local-first sync engine."`
- `imported_sources = ["README.md", ".github/CODEOWNERS", ".github/SECURITY.md"]`
- `inferred_fields = []`
- `owners.maintainers = ["@orbit-maintainer"]`
- `owners.security_contact = "security@example.com"`
- Overlay import lands as `record.status = "imported"` with `record.trust.provenance = ["imported"]`

## `badge-heavy-readme`

Surfaces present:
- `README.md`
- `SECURITY.md`

Current import summary:
- `repo.name = "Crate Atlas"`
- `repo.description = "Declarative release automation for Cargo workspaces."`
- `imported_sources = ["README.md", "SECURITY.md"]`
- `inferred_fields = []`
- `owners = none`
- `owners.security_contact = "https://example.com/security"`
- Overlay import lands as `record.status = "imported"` with `record.trust.provenance = ["imported"]`

This case is useful because the current README parser already skips leading
badge and image lines before picking the first title and description.

## `root-conventional-files`

Surfaces present:
- `README.md`
- `CODEOWNERS`
- `SECURITY.md`

Current import summary:
- `repo.name = "Harbor"`
- `repo.description = "Imported repository metadata; review and refine before relying on it."`
- `imported_sources = ["README.md", "CODEOWNERS", "SECURITY.md"]`
- `inferred_fields = ["repo.description"]`
- `owners.maintainers = ["@harbor-maintainer", "@docs-team", "docs@example.com"]`
- `owners.security_contact = "https://github.com/acme/harbor/security/policy"`
- Overlay import lands as `record.status = "inferred"` with `record.trust.provenance = ["imported", "inferred"]`

This is the current baseline for root-level conventional files and for cases
where a title imports cleanly but the description still falls back.

## `description-only-readme`

Surfaces present:
- `README.md`

Current import summary:
- `repo.name = "description-only-readme"`
- `repo.description = "Lightweight release notes generator for Git repositories."`
- `imported_sources = ["README.md"]`
- `inferred_fields = ["repo.name"]`
- `owners = none`
- Overlay import lands as `record.status = "inferred"` with `record.trust.provenance = ["imported", "inferred"]`

This is the current baseline when README prose is strong enough to import a
description but not strong enough to infer an explicit project title.

## `security-contact-unknown`

Surfaces present:
- `README.md`
- `.github/SECURITY.md`

Current import summary:
- `repo.name = "Lantern"`
- `repo.description = "Release health dashboards for CLI tools."`
- `imported_sources = ["README.md", ".github/SECURITY.md"]`
- `inferred_fields = []`
- `owners.maintainers = []`
- `owners.security_contact = "unknown"`
- Overlay import lands as `record.status = "imported"` with `record.trust.provenance = ["imported"]`

This is the baseline for the current `SECURITY.md` behavior when a policy file
exists but the importer cannot parse an email address or URL. The placeholder
is intentional and should stay explicitly explained in overlay evidence.

## `no-conventional-surfaces`

Surfaces present:
- no importable conventional files

Current import summary:
- `repo.name = "no-conventional-surfaces"`
- `repo.description = "Imported repository metadata; review and refine before relying on it."`
- `imported_sources = []`
- `inferred_fields = ["repo.name", "repo.description"]`
- `owners = none`
- Overlay import lands as `record.status = "inferred"` with `record.trust.provenance = ["inferred"]`

This is the pure fallback case for measuring whether future heuristics reduce
the number of inferred defaults.

## `mixed-codeowners`

Surfaces present:
- `README.md`
- `CODEOWNERS`

Current import summary:
- `repo.name = "Driftwood"`
- `repo.description = "Repository metadata linter."`
- `imported_sources = ["README.md", "CODEOWNERS"]`
- `inferred_fields = []`
- `owners.maintainers = ["@maintainer", "@org/release-team", "security@example.com", "@docs-team"]`
- `owners.security_contact = none`
- Overlay import lands as `record.status = "imported"` with `record.trust.provenance = ["imported"]`

This is the baseline for the current CODEOWNERS parser: it preserves unique
`@` handles and email tokens in encounter order, but it does not turn
CODEOWNERS emails into `owners.security_contact`.
