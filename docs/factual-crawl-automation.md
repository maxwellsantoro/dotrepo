# Factual Crawl Automation

This document describes the crawler's factual extraction and adjudication
architecture. Product sequencing and milestone gates live in
[`ROADMAP.md`](../ROADMAP.md).

The design follows these durable constraints:

- deterministic extraction remains the default path
- synthesis remains optional and subordinate
- source materials remain primary; overlays must not claim more certainty than
  their provenance supports

See [`docs/trust-model.md`](./trust-model.md) for the record status ladder,
provenance categories, and authority handoff rules that constrain this design.
See [`docs/import-baseline-audit.md`](./import-baseline-audit.md) for the
fixture pack that defines correct importer behavior, including intentionally
incomplete cases.

## Implemented pipeline

The crawler fetches, materializes, imports, and writes back overlay records
for public GitHub repositories. The import heuristics in `dotrepo-core` extract
name, description, build/test commands, owners, security contact, and docs
links from README, CODEOWNERS, SECURITY.md, manifest files, and workflow YAML.
Post-cleaners run after extraction to catch cross-repository error patterns.
Regression behavior belongs in the fixture pack rather than a copied scorecard
in this document.

Missing fields are often legitimately absent. The fixture audit treats
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
Deterministic verification
  identity/path/homepage consistency
  source-file existence checks
  candidate provenance checks
  exact-match verification for contacts, owners, docs links
  workflow/manifest agreement checks
        │
        ▼
Field-level scoring
  Each field gets one of four scores:
    high-confidence present
    medium-confidence present
    high-confidence absent/unknown
    unresolved
        │
        ▼
Narrow adjudication (only on unresolved fields)
  Model sees: field name + candidate values + short source snippets
  Model returns: { value, confidence, reason } or null
  Model must not invent values outside the candidate set.
        │
        ▼
Deterministic post-check
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

No LLM involvement was needed in the 50-repository audit. The pipeline (README
parser + post-cleaners + GitHub API fallback) produced correct results for that
baseline. Future improvements to the README parser or post-cleaners should
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

### Provider tiers and budgets

Routing is capability-based rather than tied to model names:

1. deterministic extraction and candidate generation
2. lowest-cost local adjudicator that satisfies the structured-output contract
3. independent second opinion when confidence or agreement policy requires it
4. stronger remote adjudicator for the bounded difficult tail

Provider choices and prices are runtime configuration. The durable contract is
that every run enforces model-call and cost ceilings, records tier and usage,
and stops escalation when a budget is exhausted. Most repositories should use
no model at all.

The scheduled autonomous refresh workflow starts OpenRouter-backed adjudication
sidecars only when `OPENROUTER_API_KEY` and tier-specific model variables are
configured. `DOTREPO_ADJUDICATION_MODEL` enables the primary tier,
`DOTREPO_ADJUDICATION_SECOND_OPINION_MODEL` enables the independent
second-opinion tier, and `DOTREPO_ADJUDICATION_API_MODEL` enables the stronger
remote escalation tier. The batch runner enforces a batch-wide hard ceiling
with `INDEX_MAX_BATCH_ADJUDICATION_CALLS` (or `--adjudication-call-budget`) and
caps each repository's `INDEX_MAX_ADJUDICATION_CALLS` to the remaining budget.
Once the budget is exhausted, provider URLs are removed for the rest of the
batch so deterministic refresh and writeback can continue without additional
model calls.

Autonomous refresh batches prefer head-aware scheduled refreshes, then fill any
open batch slots with lower-confidence checked-in records from the quality
queue. This sends `draft`, `inferred`, `imported`, low/medium-confidence, or
missing build/test/security records back through the same crawl, verification,
promotion, writeback, and telemetry conveyor instead of creating a separate
manual review path. The selected-batch metadata records any
`qualityReprocessSupplement` entries that were added.

If batch slots remain after refresh and quality reprocessing, discovery can add
new repositories directly to the same target list. Newly discovered candidates
are skipped when a `record.toml` already exists, and any accepted candidates are
recorded in selected-batch metadata as a `discoverySupplement`. They are then
crawled with `--write`, so only records passing the autonomous writeback gate
land in the index.

## Publish semantics

### Auto-promote to verified overlay

A record auto-promotes to `verified` when **every** field is either:

- high-confidence present, or
- high-confidence absent/unknown with explicit justification

This is the key condition. It is not "all fields are filled." It is "all fields
are honestly resolved."

Once promoted, the record sits above `reviewed` overlays in the precedence ladder
(see "Automated verified precedence contract" below). This means an auto-minted
`verified` overlay will be preferred over a human-reviewed overlay for the same
repository. Consumers that need human-reviewed records should check provenance for
the `"reviewed"` tag rather than relying on status alone.

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

## Implemented invariants

The test suite verifies that:

- The deterministic verification pass catches all identity/path/homepage
  inconsistencies that `validate-index` currently catches, plus source-file
  provenance checks.
- Field scoring produces one of four states for every field on every crawled
  repo, with "high-confidence absent" properly distinguished from "unresolved."
- The build/test 4-tier trust hierarchy (Manifest > ContribDoc > TaskScript >
  Workflow) resolves manifest-vs-workflow conflicts deterministically.
- Security contact detection covers CONTRIBUTING.md and issue templates without
  coercing general channels into security contacts.
- Narrow adjudication with deterministic post-check rejects out-of-candidate
  values and maps null responses to absent.
- Auto-promoted `verified` records pass the same `validate-index` checks that
  imported records pass.
- No auto-promoted record claims `reviewed` or `canonical` status.
- Promotion never rewrites field values, erases provenance origins, or changes
  record authority semantics (mode, source). See invariant tests in
  `crates/dotrepo-core/tests/auto_publish.rs`.

## Automated verified precedence contract

The automation pipeline can mint `verified` status without human involvement.
This has a protocol-level consequence that consumers must understand:

**Precedence ladder** (from [`docs/trust-model.md`](./trust-model.md)):
canonical `.repo` → canonical mirror → **verified overlay** → reviewed overlay → imported overlay → inferred overlay → draft

An auto-verified overlay **outranks a reviewed overlay**. This is intentional and
correct because:

1. **Auto-verified means "all fields honestly resolved by the deterministic pipeline,"** not "human-reviewed." The verification standard is exhaustive field-level scoring where every field is either high-confidence present or high-confidence absent with justification.

2. **Reviewed means "a human looked at this."** Human review is valuable for nuance and judgment calls, but does not guarantee the same exhaustive field-level coverage that the automated pipeline enforces.

3. **Canonical still outranks both.** A maintainer-owned `.repo` file at the repository root always wins. The automated pipeline never mints canonical status.

4. **Promotion is one-directional.** The pipeline never downgrades an existing `reviewed` or `canonical` record. If a record already has higher authority, the promotion function is a no-op. See the invariant test family in `crates/dotrepo-core/tests/auto_publish.rs` for the contract enforcement.

5. **Provenance is preserved.** Promotion appends `"verified"` to the provenance array and upgrades confidence to `"high"`, but never erases existing provenance origins. A record that was `["imported"]` becomes `["imported", "verified"]`.

### Promotion telemetry

These metrics should be tracked as the pipeline operates at scale:

- **Eligible count over time**: how many records per crawl batch are promotion-eligible
- **Blocker histogram over time**: which fields most commonly prevent promotion (unresolved or medium-confidence)
- **Promotion rate by refresh batch**: what fraction of crawled records are promoted
- **Adjudication invocation rate**: how often the model path is needed
- **Zero-model-use fraction**: how many verified records were created without any model involvement

Scheduled autonomous batches retain these run metrics in
`index/telemetry/autonomous-runs.ndjson` and publish an aggregate summary in
`index/telemetry/autonomous-summary.json`. The retained summary tracks total
crawls, writes, failures, quality-reprocess queue entries, discovery queue
entries, adjudication calls, token use, zero-model rate, promotion rate,
repositories by adjudication tier, model-budget exhaustion runs, grouped failure
classes, worst retained-run failure/adjudication/escalation rates, and repeated
failure fingerprints with suggested regression fixture slugs. Repeated
scheduled runs can demonstrate cost, resolution, and regression trends instead
of only exposing a short-lived artifact for the latest run, and recurring
failures can be converted into deterministic parser or fixture work. The runner
also writes the recurring failure backlog to
`index/telemetry/regression-fixture-candidates.json` and
`index/telemetry/regression-fixture-candidates.md` for review and fixture
creation. It also creates one checked-in stub directory per recurring failure
under `index/telemetry/regression-fixture-stubs/`; each stub contains
machine-readable metadata and a materialization checklist so the failure can be
turned into a real source fixture and deterministic fix.

Each recurring failure is also classified by **ecosystem** (rust, node, python,
go, jvm, ruby, php, dotnet, elixir, erlang, cpp, or `unknown`) inferred from the
manifest and language signals in the failure text, and by **fixture
eligibility**. Only `parser`, `evidence`, and `validation` defects are
fixture-eligible — they can be reproduced by a checked-in source fixture run
through the deterministic import pipeline. `provider`, `infrastructure`, and
`writeback` defects are environmental and are tracked for operator awareness
without becoming source fixtures. The aggregate summary cross-tabulates failures
as `failureClassesByEcosystem` and `failureEcosystems` so recurring
deterministic defects can be prioritized by ecosystem.

The stub-to-fixture loop is now completable end to end:

1. Telemetry emits a recurring-failure stub with its ecosystem and eligibility.
2. `scripts/materialize_regression_fixture.py --repo <host/owner/repo> --slug
   <fixture>` captures the conventional source files the crawler materializes
   (README, CODEOWNERS, SECURITY, manifests, workflows) into a checked-in
   fixture directory and derives an `expectation.json` by running the overlay
   import pipeline in a throwaway copy and parsing the result with `tomllib`, so
   the fixture pins the conveyor's actual parser behavior.
3. `crates/dotrepo-core/tests/regression_fixture_pack.rs` discovers each
   checked-in fixture and replays the offline overlay import path against it,
   asserting the pinned fields. The harness no-ops when empty and asserts only
   the fields each `expectation.json` declares, so the checked-in canary set can
   grow one fixture at a time across ecosystems. New captures also record
   `captured_at` and `captured_files`, and when `origin`, `fingerprint`,
   `captured_at`, or `captured_files` metadata is present, the harness validates
   that lineage too, so captured canaries keep their telemetry context and
   source-file inventory as they move from stub to checked-in regression
   fixture.

`scripts/check_autonomous_telemetry_gate.py` evaluates the retained summary
against the Milestone 1 proof thresholds: repeated runs, processed repository
volume, direct writeback activity, verified promotion activity, failure rate,
model adjudication rate, second-opinion adjudication rate, strong remote
escalation rate, exhausted adjudication budgets, fixture-eligible recurring
failures, and zero-model deterministic rate. The gate also verifies that it is
reading the current retained-summary schema and required proof fields before
treating aggregate rates as proof, and checks worst retained-run failure,
adjudication, second-opinion, and strong remote escalation rates so a bad run
cannot be hidden by favorable aggregate totals. The JSON and Markdown gate
reports include the configured threshold set and a pass/fail check summary, so a
retained artifact can be audited without recovering the original CI command
line.
Environmental recurrences such as provider or infrastructure failures remain
visible in the retained summary, but strict proof requires parser, evidence, and
validation recurrences to be fixed or converted into checked-in fixtures instead
of remaining as unresolved fixture candidates. Scheduled runs publish the gate in
warn-only mode while evidence is accumulating; a strict run without
`--warn-only` is the release-quality proof that the autonomous factory is
operating inside its stated bounds.

These surfaces show whether optional synthesis would address a real bottleneck
or duplicate work the factual pipeline already handles.

## Non-goals

- README/name/description LLM adjudication (already solved deterministically)
- Whole-repo model analysis or open-ended generation
- Auto-merge to `reviewed` or `canonical` status
- Structured discovery or ranking semantics
- Schema expansion driven only by crawler convenience
- Bundle mode, workspace, or relations support

## Related docs

- [`docs/trust-model.md`](./trust-model.md) — record status ladder and
  provenance categories
- [`docs/import-baseline-audit.md`](./import-baseline-audit.md) — fixture pack,
  intentionally incomplete cases
- [`ROADMAP.md`](../ROADMAP.md) — direction and active execution order
- [`index/review-checklist.md`](../index/review-checklist.md) — review
  standards for overlay records
