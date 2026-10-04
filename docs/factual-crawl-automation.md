# Factual crawl automation

This guide describes the current source branch's factual pipeline and operator
controls. [The roadmap](../ROADMAP.md#active-execution-order) owns product
sequencing. [Release compatibility](release-compatibility.md) explains safeguards
absent from stable binaries and older records.

Deterministic extraction is the default; source materials remain primary, models
choose grounded candidates, and synthesis cannot overwrite facts. Routine
generated records use machine gates. Humans define policy, audit the system,
and review maintainer authority claims.

## Pipeline and source boundaries

```text
discover or schedule
  -> capture repository identity and HEAD
  -> materialize bounded evidence at that commit
  -> core import and GitHub metadata reconciliation
  -> deterministic verification and field scoring
  -> bounded escalation for unresolved fields
  -> candidate/source/field post-checks and validation
  -> partial writeback, verified promotion, or abstention
  -> retain telemetry, validate index, gate public export
  -> test exact automation commit, land, deploy, verify
```

Missing HEAD or redirected repository identity aborts the crawl. File reads use
the captured commit; mutable GitHub metadata has separate retrieval context.
Fresh assessments govern refresh outcomes; a previous verified label cannot
preserve facts that no longer pass. Autonomous planning/writeback reject native,
reviewed, and canonical records.

Core owns import, verification, scoring, and promotion. The
[crawler](../crates/dotrepo-crawler/README.md) wires GitHub, materialization,
providers, telemetry, and writeback. The
[import fixture guide](import-baseline-audit.md) explains intentional incomplete
cases and exact regression expectations.

### Extraction policy

- Name and description use deterministic parsing/cleaning and GitHub metadata
  reconciliation. Keep promotional headings and incidental links out of facts.
- Build/test candidates use the source hierarchy: manifest, contributor docs,
  root task script, workflow. A source tier does not prove repository-wide scope.
  Scalar defaults withhold nested commands, documented directory changes,
  component CI working directories, placeholders, dangling continuations, and
  setup-only flags; preserve prerequisites rather than stripping them away.
- Security extraction distinguishes actionable private reporting channels from
  support, issue, and social channels. `unknown` remains an honest result.
- Ownership retains explicit maintainers/team context; competing broad teams
  must not become an invented single team.
- Documentation requires a supporting declaration and retained context;
  URL shape or a dependency link alone does not establish project ownership.

Ambiguous ecosystem commands can remain in additive candidate arrays, with
primary build/test unset. [RFC 0020](../rfcs/0020-multi-ecosystem-command-candidates.md)
describes that subset; candidates do not supply working directory, scope, or
prerequisites. Command screening is heuristic, not a sandbox or proof of execution.
Sandbox verification is not a routine implemented crawler stage.

## Scoring and publication gates

The scorer has five dispositions, defined in
[`import/types.rs`](../crates/dotrepo-core/src/import/types.rs) and applied in
[`import/fields.rs`](../crates/dotrepo-core/src/import/fields.rs):

| Disposition | Meaning | Verified promotion |
| --- | --- | --- |
| High-confidence present | Supported value at the pipeline's highest assessment level | Allowed |
| Medium-confidence present | Plausible value with remaining inference/ambiguity | Blocks |
| High-confidence absent | No supported value found in inspected material | Allowed |
| Suspect | Present value with a detected quality problem | Blocks |
| Unresolved | Conflict or insufficient evidence | Blocks |

Not-found means absent from inspected sources, not universally absent. Confidence
is a pipeline assessment, not a calibrated correctness probability. Conventional
ecosystem defaults are inference; direct manifest presence does not make every
command extracted or high-confidence.

**Writeback** (`autonomous_writeback_eligible`) requires deterministic verification
and permits honestly partial overlays. **Promotion**
(`eligible_for_auto_publish`) additionally requires no unresolved, suspect, or
medium-confidence fields. Promotion preserves facts and provenance, appends
verification context, and never mints reviewed/canonical authority. Reviewed and
canonical records are protected rather than autonomously replaced.

Fresh crawls retain value- and timestamp-bound field evidence. Export drops
assessments that no longer match; legacy high-confidence labels cannot substitute
for retained evidence. Read-only `promotion-report` uses those assessments;
standalone `--apply` is disabled on this branch. See
[trust semantics](trust-model.md#field-assessments-and-the-meaning-of-verified)
for the release distinction, selection precedence, and consumer implications.

## Model integration and budgets

Only unresolved fields escalate. Providers receive the requested field, allowed
candidate values/sources, and bounded source excerpts. A selected value must
match a grounded candidate and the requested field; invented values or sources
fail deterministic post-checks. Confident absence can terminate escalation;
low-confidence absence/rejection continues when policy and budget permit.
See [`import/escalation/`](../crates/dotrepo-core/src/import/escalation/).

The tier order is deterministic resolution, bounded primary adjudicator,
independent second opinion, then stronger remote adjudicator. Provider/model
identity is runtime configuration, not a protocol constant. Most repositories
should require no model. Failed/timed-out attempts count against call budgets.

The scheduled workflow starts OpenRouter sidecars when `OPENROUTER_API_KEY` and
tier-specific model variables exist:

- `DOTREPO_ADJUDICATION_MODEL`: primary tier
- `DOTREPO_ADJUDICATION_SECOND_OPINION_MODEL`: second opinion
- `DOTREPO_ADJUDICATION_API_MODEL`: stronger remote tier

The batch hard ceiling is `INDEX_MAX_BATCH_ADJUDICATION_CALLS` or
`--adjudication-call-budget`; each repository's `INDEX_MAX_ADJUDICATION_CALLS`
is capped by the remaining budget. On exhaustion the runner removes provider
URLs for remaining repositories, allowing deterministic partial progress.
Configuration and provider contracts live in
[`adjudication.rs`](../crates/dotrepo-crawler/src/adjudication.rs) and
[the sidecar](../scripts/adjudication_openrouter_sidecar.py).
A configured hosted primary tier is not evidence that a local model ran.

The local sample configuration uses `openai/gpt-6-luna` for primary adjudication,
`qwen/qwen3.8-flash` for second opinions, and `z-ai/glm-5.3-flash`
for tail escalation. These are operator selections, not measured quality rankings.
GitHub Actions still requires explicit repository variables; `.env.example` does
not enable remote tiers or replace call-budget and automation opt-ins.

The sidecar and head-to-head benchmark share
[`openrouter_request_policy.py`](../scripts/openrouter_request_policy.py).
Luna uses low reasoning effort with a 4,096-token total completion cap. Qwen's
second opinion requests a 1,024-token reasoning budget within 4,096 total tokens;
GLM's tail uses high effort with 8,192 tokens. Reasoning shares the output budget.
Mandatory reasoning is never disabled, and Luna omits temperature. Gemini3.8 Flash
has an alternative profile for explicit model overrides.
The three selected tiers also enforce provider price ceilings at their reviewed
rates; unavailable cheap routes fail instead of silently spending more on fallback.
Reviewed models use candidate-constrained JSON schemas for adjudication and
require providers to support requested parameters. Core still checks the selected
source/value pair; schema validation alone cannot establish factual correctness.

Per-call logs retain returned model/provider, generation ID, finish reason,
input/output/reasoning tokens, and cost when reported. Logs exclude candidates,
prompts, and credentials, and scheduled artifact uploads retain sidecar logs.
Billed truncated, empty, or malformed answers are provider failures rather than
honest absence: their returned token usage survives HTTP errors into the crawl
report, and subsequent tiers may run within the same attempt budget. Unknown
usage is not estimated. Logs are separate from aggregate batch token telemetry.
Historical model results and frozen benchmark inputs remain unchanged.

The [October 4 integration canary](../benchmarks/model-adjudication/2026-10-04/requests.json)
retains three synthetic cases, both prompt revisions, and the initial and follow-up
results. Luna passed all three initial cases. GLM first chose a broader command
without evidence of primacy; after clarifying the abstention rule it passed all
three. Muse was rejected before inference by the configured account's paid-model
training restriction. Muse was then removed from the active configuration in
favor of Qwen3.8 Flash, preserving the account policy. These
small provider checks do not establish real-repository accuracy or consumer proof.
The [Qwen second-opinion follow-up](../benchmarks/model-adjudication/2026-10-04/qwen-second-opinion-reasoning-canary.json)
passed all three cases using the bounded reasoning profile. Its initial run without
reasoning conservatively abstained on the normal-CI-versus-release case; that
[initial result](../benchmarks/model-adjudication/2026-10-04/qwen-second-opinion-canary.json)
is also retained.

### Optional synthesis

Configure `DOTREPO_SYNTHESIS_URL` and opt in with crawler/batch `--synthesize`,
`--synthesis-model`, and `--synthesis-provider` (or the corresponding
`DOTREPO_SYNTHESIS_MODEL` / `DOTREPO_SYNTHESIS_PROVIDER` variables).
`DOTREPO_SYNTHESIS_API_KEY` supplies a Bearer token when present.

The request includes validated facts and at most 12 documents, each capped at
32,000 characters and 128,000 aggregate characters. The sidecar may return
`architecture` and `forAgents` guidance plus token usage. Crawler-owned time,
revision, provider context, and factual commands cannot be overridden. Unknown
fields, unsafe/ungrounded entry points, fact conflicts, and schema/bounds failures
are rejected before `synthesis.toml` writeback. Failures are retained while factual
publication continues. See [the implementation](../crates/dotrepo-crawler/src/synth.rs)
for exact request/response types and validation.

## Scheduling and local operation

Refresh prioritizes oldest factual crawls and inspects at most `--limit`
repositories. Same-HEAD records qualify after 14 days, leaving headroom before
the public 30-day record-age policy. Index membership takes precedence over stale
crawler-state identities. Identity migrations are separately evidenced in
[`index/identity-migrations.json`](../index/identity-migrations.json).

Open batch slots can take oldest quality-queue records, then discovery candidates
when discovery is enabled. Selection metadata retains `qualityReprocessSupplement`
and `discoverySupplement`; partial records share the same pipeline rather than a
separate review queue. The scheduled workflow currently disables discovery.

An explicit local batch writes index/telemetry state and eligible records:

```bash
uv run python scripts/run_autonomous_index_batch.py \
  --skip-automation-enabled-check \
  --disable-discovery \
  --output-dir /tmp/dotrepo-autonomous-batch
```

For explicitly requested stale catch-up:

```bash
uv run python scripts/refresh_stale_index.py --limit 1000 \
  --output-dir /tmp/dotrepo-stale-catchup
```

Catch-up uses four workers, isolated worker state, and validation after each
50-record cohort; models and discovery are disabled. Credentials must already
be configured. Record timestamps change only after actual crawls.

### Scheduled enablement and landing

[`index-autonomous-refresh.yml`](../.github/workflows/index-autonomous-refresh.yml)
runs daily at 06:00 UTC with a default 50-record inspection/crawl budget, only
when `INDEX_AUTOMATION_ENABLED=true`. Unset disables the workflow. Local runners
also default disabled unless explicitly opted in. The built-in `GITHUB_TOKEN`
needs contents, pull-request, and actions write permissions; repository Actions
must be allowed to create PRs.

The workflow retains telemetry and valid partial writes even when repositories
fail. Strict telemetry, index validation, and the public-surface gate must pass
before opening a non-draft automation PR. There is no routine human merge tier.
[`land_autonomous_index.py`](../scripts/land_autonomous_index.py):

1. Requires a same-repository, index-only PR matching expected head and base.
2. Dispatches CI explicitly, waits for its run, and requires the public gate to
   succeed for that exact commit.
3. Rechecks the PR/default branch and fast-forwards with `force: false`.
   Divergence or branch protection rejects landing; it does not bypass settings.
4. Dispatches deployment and waits for the deploy job and smoke check.

Explicit dispatch is necessary because ordinary `GITHUB_TOKEN` pushes do not
start downstream push workflows. A successful crawl is not publication proof.
If the base advanced, regenerate the batch. If landing succeeded but deployment
failed, rerun deployment. The workflow restores the failed batch result after
retaining evidence; partial progress does not silently turn a failure green.

A nominal 50-record daily capacity is not proof of successful rotation.
Monitor actual cadence and backlog. Release freshness fails when over 10% of
exported records are stale or unknown; a new export cannot reset factual age.
The gate evaluates at the current check time and also fails if any known record
age exceeds the 30-day policy by more than seven days. Reports retain export and
evaluation timestamps separately and identify overdue repositories. Use
`check_public_record_freshness.py --now <timestamp-with-timezone>` for a
reproducible historical evaluation; this override does not refresh facts.

### Writeback recovery

Persistence uses a per-record `.writeback.lock`, stages sibling artifacts, and
backs up existing files before commit. I/O failure triggers rollback; rollback
failure retains backups and reports recovery paths. This is not crash-atomic.
After a crash inspect the lock, staged files, and backup siblings, restore a
consistent artifact set, then remove the lock and retry. See
[`writeback.rs`](../crates/dotrepo-crawler/src/writeback.rs).

## Telemetry and quality feedback

Runs append to `index/telemetry/autonomous-runs.ndjson`; the retained aggregate
is `autonomous-summary.json`. The runner records crawl/write/failure outcomes,
selection supplements, promotion, model calls/tokens/tier mix, exhausted budgets,
synthesis outcomes, and repeated failure fingerprints. Summary schema and
required proof fields are validated by
[`check_autonomous_telemetry_gate.py`](../scripts/check_autonomous_telemetry_gate.py).

The gate checks aggregate, worst-run, and recent-window failure/tier rates and
compares recent to previous windows. Fixture-eligible recurrent defects require
fixes or fixtures. Scheduled runs use strict mode; `--warn-only` is a diagnostic
option and does not establish release-quality proof. Run/gate artifacts retain
thresholds and checks for later audit.

### Unit costs

```bash
uv run python scripts/render_unit_cost_report.py \
  --runs index/telemetry/autonomous-runs.ndjson
```

Per-crawl telemetry includes wall time, GitHub requests/bytes, child CPU, and
best-effort peak process-group RSS. Legacy missing resource fields remain `n/a`.
Categories are `unchanged` (scheduler skip), `changed` (recrawl without status
advance), and `improved` (status advance). These are proxies: zero-cost skip rows
exclude planning/head checks, and status advancement is not a field-quality or
task-success measurement. Include those omitted costs in scale and consumer proof.

### Regression conversion

Failure classes retain ecosystem tags and fixture eligibility. Parser, evidence,
and validation defects can become source fixtures; provider, infrastructure, and
writeback defects remain operational issues. Backlog/stubs live under
`index/telemetry/regression-fixture-candidates.*` and `regression-fixture-stubs/`.

```bash
uv run python scripts/materialize_regression_fixture.py \
  --stub index/telemetry/regression-fixture-stubs/<fixture> \
  --repo <host/owner/repo>
```

One retained identity can be selected automatically; multiple identities require
an explicit choice, and conflicting provenance is rejected. Captures retain
source files, timestamps, hashes, and expectations from the overlay import path.
`regression_fixture_pack.rs` replays them offline and checks lineage where present.
A capture pins behavior; inspect its expected facts before treating it as a fix.
The deterministic pack covers Rust, JS/TS, Python, Go, JVM, Ruby, PHP, .NET,
Elixir, Erlang, and CMake. Ecosystem-specific extraction rules live in
[`commands/extraction.rs`](../crates/dotrepo-core/src/import/commands/extraction.rs).

### Audit cadence

Weekly or after a full-population recrawl, draw a reproducible risk-weighted
sample. The sampler is read-only/local-only; it performs no model adjudication
or automatic correction:

```bash
uv run python scripts/audit_index_sample.py \
  --index-root index \
  --output-json "index/telemetry/audit-sample-$(date -u +%Y%m%d).json" \
  --output-md "index/telemetry/audit-sample-$(date -u +%Y%m%d).md"
```

Inspect against [the manual audit rubric](../index/review-checklist.md).
Convert actionable findings into fixtures, deterministic fixes, calibration,
or an explicit policy disposition; do not create per-record approval queues.
The full-index documentation audit also runs independently of random sampling:

```bash
uv run python scripts/audit_index_sample.py --sample-size 0 --seed 1 \
  --output-json /tmp/dotrepo-docs-audit.json --output-md /tmp/dotrepo-docs-audit.md
uv run python scripts/render_intent_quality_scorecard.py --index-root index
uv run python scripts/render_coverage_gaps.py --index-root index --limit 50
```

Documentation evidence/origin flags are source-inspection signals; custom/shared
domains can be legitimate. Scorecards complement sampling and independent
accuracy tests. See [the escalation canary](m1-escalation-canary.md) for live
tier proof and [distribution](distribution.md) for exported lookup-miss demand.
