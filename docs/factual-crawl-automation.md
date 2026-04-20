# Factual Crawl Automation

This document describes how the crawler's factual extraction pipeline should
scale from its current boutique review loop to a high-throughput system that
publishes honest partial records without requiring human review on every merge.

The plan stays aligned with the project's current priorities:

- deliberate index growth is the active top priority
- crawler completion is later work
- synthesis remains optional and subordinate
- source materials remain primary; overlays must not claim more certainty than
  their provenance supports

See [`docs/trust-model.md`](./trust-model.md) for the record status ladder,
provenance categories, and authority handoff rules that constrain this design.
See [`docs/import-baseline-audit.md`](./import-baseline-audit.md) for the
fixture pack that defines correct importer behavior, including intentionally
incomplete cases.

## Current state

The crawler fetches, materializes, imports, and writes back overlay records
for public GitHub repositories. The import heuristics in `dotrepo-core` extract
name, description, build/test commands, owners, security contact, and docs
links from README, CODEOWNERS, SECURITY.md, manifest files, and workflow YAML.
Three universal post-cleaners (name, description, URL quality) run after
extraction to catch cross-repo error patterns.

Across 50 repos in the current index:

| Field        | Present | Notes                                   |
|--------------|---------|-----------------------------------------|
| name         | 50/50   | 100% after cleaners                     |
| description  | 50/50   | 100% after cleaners                     |
| homepage     | 50/50   | some are GitHub URLs                    |
| build        | 27/50   | correct when present, unset on conflict |
| test         | 27/50   | correct when present, unset on conflict |
| security     | 29/50   | correct when present                    |
| owners       | 30/50   | correct when present                    |
| docs links   | ~30/50  | URL quality enforced by `is_quality_url`|

Missing fields are often legitimately absent. The fixture audit already treats
`security_contact = "unknown"` and `owners.team = none` as intentionally
incomplete in some cases. See
[`docs/import-baseline-audit.md`](./import-baseline-audit.md) under
"Intentionally incomplete cases" for the canonical examples.

## Pipeline

```
Deterministic crawl
  GitHub API fetch → materialize → import heuristics → post-cleaners
  → merge GitHub metadata → validate → write back
        │
        ▼
Deterministic verification  (NEW)
  identity/path/homepage consistency
  source-file existence checks
  candidate provenance checks
  exact-match verification for contacts, owners, docs links
  workflow/manifest agreement checks
        │
        ▼
Field-level scoring  (NEW)
  Each field gets one of four scores:
    high-confidence present
    medium-confidence present
    high-confidence absent/unknown
    unresolved
        │
        ▼
Narrow adjudication  (NEW, only on unresolved fields)
  Model sees: field name + candidate values + short source snippets
  Model returns: { value, confidence, reason } or null
  Model must not invent values outside the candidate set.
        │
        ▼
Deterministic post-check  (NEW)
  Chosen value must come from the candidate set.
  Cited snippet must actually exist in fetched files.
  Normalized value must parse.
  Sandbox execution upgrades provenance, does not replace it.
        │
        ▼
Publish
  verified overlay:   every field is high-confidence present OR
                      high-confidence absent/unknown
  imported/inferred:  unresolved fields remain
  reviewed:           human-reviewed only
```

### Key design rules

1. **Never spend tokens to answer a question the filesystem, GitHub API, or a
   sandbox can answer more reliably.**
2. **Treat "confidently absent" as a success state.** A repo without a SECURITY.md
   that gets `security_contact` scored as high-confidence absent is resolved, not
   broken.
3. **Do not coerce general signals into specific fields.** A general support
   channel is not a security contact. A broad multi-team CODEOWNERS file is not
   a single `owners.team`.
4. **Keep synthesis subordinate.** The model path is narrow adjudication on
   unresolved fields, not whole-repo analysis.
5. **Preserve visible incompleteness.** The fixture audit and import baseline
  both treat some absences as intentional. Scoring and auto-publish must not
  quietly normalize those away.

## Field-specific plans

### Name and description

No LLM involvement needed. The current pipeline (README parser + post-cleaners
+ GitHub API fallback) produces correct results for 100% of the current 50
repos. Future improvements to the README parser or post-cleaners should
continue to be deterministic.

### Build and test

This is primarily a source-trust ranking problem, not an LLM problem. The
current approach leaves fields unset when multiple candidates conflict. A trust
hierarchy resolves most of these without any model:

1. Direct project manifest / top-level tool config
   (`Cargo.toml`, `package.json`, `pyproject.toml`, `go.mod`)
2. Repo-local contributor docs (`CONTRIBUTING.md`, `BUILDING.md`)
3. Root-level task scripts (`Makefile`, `Justfile`)
4. CI workflow files as corroboration or fallback
5. Language/stack sanity checks
6. Sandbox execution as the strongest verifier

The hierarchy avoids over-trusting CI when CI tests only sub-packages or
matrices, but also avoids under-trusting it when CI is the only real evidence.

When the hierarchy still leaves multiple candidates, the field stays unresolved
and may be escalated to narrow adjudication.

### Security contact

Broaden detection conservatively:

- Add `CONTRIBUTING.md` as a source
- Add `.github/ISSUE_TEMPLATE/security.md` and similar issue templates
- Add GitHub security policy links when exposed in fetched materials

Maintain a three-way distinction:

- **Private mailbox** (email address) — highest confidence
- **Policy/reporting URL** (security advisory page, disclosure form) — medium
- **Explicitly unknown** — honest absence, not a failure

Do not coerce general support channels, mailing lists, or social media accounts
into security contacts.

### Owners and team

This deserves to be a first-class ambiguity class. The fixture audit has cases
where `owners.team` should intentionally remain unset because ownership is
genuinely broad and multi-team. Score that as **high-confidence absent**, not
low-confidence failure.

When CODEOWNERS has a clear repo-wide team, score `owners.team` as
high-confidence present. When CODEOWNERS has competing broad teams, score as
high-confidence absent with justification in evidence.

### Docs links

Keep URL quality checks (localhost, anchor-only, bare domain rejection). Add
"confidently absent" scoring: a repo without good docs links is not necessarily
unresolved.

## Field scoring rules

Each field is scored independently. The score determines the field's
disposition in the publish step.

### High-confidence present

The field value came from a direct, unambiguous source with no competing
candidates:

- `repo.name` from a README `#` heading that passed the skip list and
  post-cleaners
- `repo.test` from `Cargo.toml` with no conflicting CI candidates
- `owners.security_contact` from a `mailto:` link in SECURITY.md

### Medium-confidence present

The field value came from a plausible source but with some ambiguity:

- `repo.description` from the GitHub API because README parsing failed
- `repo.test` from a CI workflow when the manifest had no test command
- `owners.security_contact` as a policy URL rather than a direct mailbox

### High-confidence absent/unknown

The field was not found, but the absence is honestly resolved:

- `owners.security_contact = "unknown"` when no SECURITY.md exists
- `owners.team` unset when CODEOWNERS has competing broad teams
- `repo.build` unset when the project is a library with no documented build
  command
- `docs.root` absent when no docs site exists

### Unresolved

The field has multiple competing candidates and no clear winner:

- `repo.test` when `Cargo.toml` says `cargo test` and CI says
  `cargo test --all-features` and the trust hierarchy does not resolve it
- `repo.build` when both `Makefile` and `Cargo.toml` provide build commands
  and neither is clearly primary

Unresolved fields may be escalated to narrow model adjudication. After
adjudication and post-check, they become either present or absent at the
model's confidence level.

## Model integration

### When the model runs

Only for unresolved fields. The model never sees the whole repo. It sees:

- the field name
- the candidate values and their sources
- short source snippets (a few lines of CI config, a SECURITY.md excerpt)

### What the model returns

```json
{
  "field": "repo.test",
  "value": "cargo test --all-features",
  "confidence": "medium",
  "reason": "CI workflow runs this as the primary check command",
  "source": "ci.yaml"
}
```

Or:

```json
{
  "field": "repo.test",
  "value": null,
  "confidence": "high",
  "reason": "candidates test different sub-crates; no single primary command"
}
```

### What happens after

Deterministic post-check:

- The chosen value must come from the candidate set.
- The cited source snippet must actually exist in the fetched files.
- If the model proposes something outside the candidate space, reject it.
- If the model returns null, score the field as high-confidence absent.

### Model stack

The model path should be rare. Most repos should never touch a model.

- **Local default adjudicator:** Gemma 4 E4B (on-device, ~9.6GB, 128K context)
- **Local second opinion:** Qwen3.5-9B (disagreement resolver)
- **API escalator:** Gemma 4 26B A4B (only for rare hard cases, not part of
  the ordinary path)

The API model should not be part of the ordinary pipeline. Its role is
escalation for the tiny tail of genuinely hard repos.

### Token budget

Most repos: 0 tokens.
Some repos: one narrow adjudication pass (~2-5K input, ~150 output).
Rare repos: one larger pass (~8K input, ~250 output).

At OpenRouter pricing, a 4K/150 adjudication pass on Gemma 4 26B A4B costs
about $0.0004. For 10,000 repos at 25% adjudication rate, total cost is under
$1.

## Publish semantics

### Auto-promote to verified overlay

A record auto-promotes to `verified` when **every** field is either:

- high-confidence present, or
- high-confidence absent/unknown with explicit justification

This is the key condition. It is not "all fields are filled." It is "all fields
are honestly resolved."

### Remain as imported/inferred

A record stays at its crawl-determined status when unresolved fields remain.
It still publishes. The index is useful through trustworthy partial records,
not through universal perfection.

### Reviewed

Reserved for human-reviewed records. The automation pipeline does not mint
`reviewed` status. That requires a human contributor or curator.

### Canonical

Reserved for maintainer-controlled in-repo records. Not in scope for this
automation plan.

## Implementation order

1. **Deterministic verification pass** — identity/path checks, source-file
   existence, candidate provenance, exact-match for contacts and owners
2. **Field-level scoring with "confidently absent" support** — per-field
   confidence, four-bucket scoring, honest absence as success
3. **Build/test source-trust hierarchy + sandbox verification** — resolve the
   23 missing build and 23 missing test fields with code, not models
4. **Broader security and owner detection** — CONTRIBUTING.md, issue
   templates, three-way contact distinction, team ambiguity as honest absence
5. **Narrow adjudication for unresolved fields** — local Gemma E4B sidecar,
   strict JSON output, deterministic post-check
6. **Auto-publish to verified overlay** — honest-resolution threshold,
   `verified` status promotion, preserve `imported`/`inferred` for partials
7. **Synthesis integration** — later, still subordinate to factual crawl

## Acceptance criteria

- The deterministic verification pass catches all identity/path/homepage
  inconsistencies that `validate-index` currently catches, plus source-file
  provenance checks.
- Field scoring produces one of four states for every field on every crawled
  repo, with "high-confidence absent" properly distinguished from "unresolved."
- The build/test trust hierarchy resolves at least 60% of the currently unset
  build/test fields without model involvement.
- Security contact detection covers CONTRIBUTING.md and issue templates without
  coercing general channels into security contacts.
- The model adjudication path is invoked on fewer than 30% of crawled repos.
- Auto-promoted `verified` records pass the same `validate-index` checks that
  imported records pass.
- No auto-promoted record claims `reviewed` status.

## Non-goals

- README/name/description LLM adjudication (already solved deterministically)
- Whole-repo model analysis or open-ended generation
- Auto-merge to `reviewed` or `canonical` status
- Public search or ranking UX
- Schema expansion beyond current post-v1 blockers
- Bundle mode, workspace, or relations support

## Related docs

- [`docs/trust-model.md`](./trust-model.md) — record status ladder and
  provenance categories
- [`docs/import-baseline-audit.md`](./import-baseline-audit.md) — fixture pack,
  intentionally incomplete cases
- [`docs/growth-and-automation-plan.md`](./growth-and-automation-plan.md) —
  operating plan for index growth cadence and automation
- [`docs/roadmap.md`](./roadmap.md) — current post-v1 priorities
- [`index/review-checklist.md`](../index/review-checklist.md) — review
  standards for overlay records
