# Import baseline audit

This document records the current import fixture pack at
`crates/dotrepo-core/tests/fixtures/import/` and the enforced expectation
snapshot at `crates/dotrepo-core/tests/fixtures/import/expectations.json`.

It began as the issue `#1` baseline and now serves issue `#26` as well: the
fixture pack is larger, but the goal is unchanged. Import behavior should be
measurable on a stable set of inputs, with the machine-readable gate in
`crates/dotrepo-core/tests/import_quality_gate.rs` acting as the canonical
regression barrier.

This document is descriptive rather than normative. The expectation snapshot is
what CI enforces; this file explains why the cases exist and which ones are
intentionally incomplete.

## Common behavior

- Native imports always land as `record.status = "draft"`.
- Overlay imports land as `record.status = "imported"` when `inferred_fields`
  is empty and `record.status = "inferred"` otherwise.
- Overlay imports always emit `evidence.md`; native imports do not.
- README heuristics are allowed to improve title, description, and minimal docs
  entry-point extraction, but should not invent canonical data.
- `CODEOWNERS` and `SECURITY.md` imports remain bootstrap metadata, not
  maintainer-verified truth.

## Coverage map

### README-focused cases

- `badge-heavy-readme`: badges and images before the first real title and
  description.
- `setext-heading-readme`: setext heading plus wrapped paragraph description.
- `html-heading-readme`: centered HTML heading and paragraph tags.
- `inline-html-wrapper-readme`: heading and description wrapped inline by HTML.
- `docs-nav-readme`: docs/getting-started navigation links should become docs
  entry points, not prose description.
- `docs-label-readme`: explicit `Docs:` and `Getting started:` labels should
  become docs entry points.
- `description-only-readme`: strong description with no explicit title.

### CODEOWNERS-focused cases

- `full-signals`: simple `.github/CODEOWNERS` happy path.
- `root-conventional-files`: root-level `CODEOWNERS` plus other conventional
  files.
- `mixed-codeowners`: repo-wide team ownership with narrower team overrides,
  preserving a primary team signal without flattening narrower owners.
- `team-heavy-codeowners`: broad multi-team ownership where `owners.team`
  should stay unset and the ambiguity should remain visible.

### SECURITY-focused cases

- `badge-heavy-readme`: root `SECURITY.md` with a policy/reporting URL.
- `root-conventional-files`: root `SECURITY.md` with a GitHub security policy
  URL.
- `security-markdown-link`: inline markdown `mailto:` link.
- `security-reference-link`: reference-style markdown `mailto:` link.
- `security-html-anchor`: HTML anchor `href="mailto:..."`.
- `security-mailto-query`: `mailto:` link with query parameters.
- `security-contact-unknown`: SECURITY file exists but exposes no parseable
  mailbox or URL.

### Fallback control

- `no-conventional-surfaces`: no importable conventional files at all.

## Intentionally incomplete cases

- `description-only-readme`: `repo.name` is inferred from the directory because
  the README never names the project directly.
- `root-conventional-files`: `repo.description` is still inferred because the
  README does not provide a usable description line.
- `security-contact-unknown`: `security_contact = "unknown"` is intentional and
  should stay explicitly justified in overlay evidence.
- `team-heavy-codeowners`: `owners.team` remains unset because broad ownership
  is genuinely multi-team.
- `no-conventional-surfaces`: both `repo.name` and `repo.description` are
  inferred defaults by design.

## Representative current outcomes

### `full-signals`

- `repo.name = "Orbit"`
- `repo.description = "Fast local-first sync engine."`
- `owners.maintainers = ["@orbit-maintainer"]`
- `owners.security_contact = "security@example.com"`
- `imported_sources = ["README.md", ".github/CODEOWNERS", ".github/SECURITY.md"]`
- `inferred_fields = []`

### `docs-nav-readme`

- `repo.name = "Tidelift"`
- `repo.description = "Policy-aware release orchestration for multi-service deploys."`
- `docs.root = "./docs/"`
- `docs.getting_started = "./docs/getting-started.md"`
- `imported_sources = ["README.md"]`
- `inferred_fields = []`

### `mixed-codeowners`

- `owners.maintainers = ["@maintainer", "@org/release-team", "security@example.com", "@org/docs-team"]`
- `owners.team = "@org/release-team"`
- trust notes explain that the repo-wide rule wins while narrower owner
  candidates remain preserved

### `team-heavy-codeowners`

- `owners.maintainers = ["@org/platform-team", "@org/release-team", "@alice", "@org/docs-team", "@org/payments-team"]`
- `owners.team = none`
- trust notes explain that broad multi-team ownership leaves `owners.team`
  unset intentionally

### `badge-heavy-readme`

- `owners.security_contact = "https://example.com/security"`
- trust notes explain that the imported value is a policy/reporting URL rather
  than a direct mailbox

### `security-reference-link`

- `owners.security_contact = "security@example.com"`
- extracted from reference-style markdown rather than raw text

### `security-html-anchor`

- `owners.security_contact = "security@example.com"`
- extracted from an HTML `href="mailto:..."` anchor

### `security-mailto-query`

- `owners.security_contact = "security@example.com"`
- extracted from a `mailto:` destination that includes query parameters

### `security-contact-unknown`

- `owners.security_contact = "unknown"`
- overlay evidence must explain that no explicit mailbox or URL was parseable

### `no-conventional-surfaces`

- `repo.name = "no-conventional-surfaces"`
- `repo.description = "Imported repository metadata; review and refine before relying on it."`
- `imported_sources = []`
- `inferred_fields = ["repo.name", "repo.description"]`

## Review guidance

When importer behavior changes, reviewers should be able to tell which of these
three things happened:

- coverage increased because a new fixture was added
- behavior improved because an existing fixture expectation changed
- both happened together, in which case the PR should say so explicitly

If a case is intentionally incomplete, the expectation snapshot should keep that
incompleteness visible rather than quietly normalizing it away.
