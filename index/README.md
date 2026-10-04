# dotrepo Public Index

This directory is the checked-in source for dotrepo's public repository index.
It is a reusable, evidence-backed cache of repository understanding for humans,
agents, and tools.

Records enter through two paths:

- the autonomous factory publishes generated overlays after deterministic
  extraction, narrow model adjudication when needed, and machine validation
- maintainers and contributors can submit native claims or evidence-backed
  overlays through the normal pull-request path

Routine generated overlays do not require human approval. Humans define the
policy and audit the system; maintainers can supersede overlays by publishing
native `.repo` metadata and completing the claim flow.

Optional bounded `synthesis.toml` guidance is a separate artifact, not a third
authority path; it cannot control factual fields.

## Layout

Each record lives under:

```text
index/
  repos/
    <host>/
      <owner>/
        <repo>/
          record.toml
          evidence.md
          synthesis.toml  # optional, bounded non-factual guidance
```

## Index rules

- Generated and contributed index entries use `record.mode = "overlay"`.
- Index entries may also carry maintainer-claim directories, but the
  checked-in seed records remain overlay records today even when the upstream
  repository publishes a native `.repo`; canonical handoff is expressed through
  claim links until the index starts carrying canonical mirrors.
- Accepted claims without canonical links remain `pending_canonical`; they show
  live maintainer intent without implying canonical authority early.
- `record.toml` must pass `dotrepo validate`.
- `evidence.md` must exist beside every `record.toml`.
- `record.source` must resolve to the same `<host>/<owner>/<repo>` path used by the index entry.
- `repo.homepage`, when it is a repository URL, must match that same identity.
- `validate-index` fails on structural and identity errors, and warns when public-index records use non-reference trust vocabulary or thin evidence.
- `evidence.md` should say what was imported, what was inferred, where build and test commands came from, and why any `unknown` placeholders are intentional.

## Documentation audit

Run the deterministic full-index documentation audit independently of sampling:

```bash
uv run python scripts/audit_index_sample.py --sample-size 0 --seed 1 --output-json /tmp/dotrepo-docs-audit.json --output-md /tmp/dotrepo-docs-audit.md
```

The `docsAudit` report checks every populated documentation field for matching
field evidence and a specific evidence note. It also flags unconfirmed URL
identity, differing docs origins, and targets matching another repository's
homepage. These are source-inspection signals, not automatic rejection rules:
custom domains and shared documentation can be legitimate. Ordinary sampled
runs include the same full audit and increase the sampling weight of flagged
records. Imports retain the selected URL's source line and context; conflicting
declarations remain unresolved rather than gaining confidence from URL syntax.

## Evidence rubric

Reference-quality `evidence.md` files should make a record auditable without
forcing a consumer or operator to reverse-engineer where claims came from.

At minimum, every overlay evidence file should:
- state what was imported directly and name the upstream source
- state what was inferred and explain the reasoning path
- explain where `repo.build` came from, even when the answer is "inferred from project layout"
- explain where `repo.test` came from, even when the answer is "inferred from project layout"
- identify each selected `docs.*` value and cite its supporting source declaration;
  a documentation-shaped URL or dependency link alone does not establish ownership
- explain why any intentional `unknown` placeholders remain, especially security contacts
- end with the reminder that the record is an overlay, not a maintainer-controlled canonical record

Reference-quality evidence should also:
- prefer source-specific citations over vague phrases like "from the repo"
- group related imported claims when they come from the same source
- avoid making inferred claims sound maintainer-verified
- make it obvious when a field is absent because the source material did not justify a stronger claim

## Starter template

Use [`index/evidence-template.md`](evidence-template.md) as the starting point for new
overlay entries, then replace each placeholder with repository-specific evidence.

Reviewers can use [`index/review-checklist.md`](review-checklist.md) for manual
submissions and audits. The autonomous conveyor uses the gates documented in
[`ROADMAP.md`](../ROADMAP.md) and
[`docs/factual-crawl-automation.md`](../docs/factual-crawl-automation.md).
The machine-readable [`index/tranche-one-targets.txt`](tranche-one-targets.txt)
is retained for reproducible first-tranche crawler runs.
[`index/tranche-two-targets.txt`](tranche-two-targets.txt) retains the completed
second-tranche catalog as historical evidence. Further corpus growth
requires a new evidence-backed candidate list; until one is checked in, seed
workflows and the roadmap batch read the current catalog from
`scripts/fixtures/index_growth_tranche_baseline.json`.
The seed command can also emit an advisory audit report via
`--review-report-md <path>`.
For maintainer-claim review, use
[`docs/maintainer-claim-review-workflow.md`](../docs/maintainer-claim-review-workflow.md)
as the end-to-end operator loop.
The live index includes
[`github.com/maxwellsantoro/ries-rs`](repos/github.com/maxwellsantoro/ries-rs/)
as the first checked-in accepted maintainer-claim example, now linked to the
upstream native `.repo`.
The operator gate still stages one copied seed entry through claim handoff and
`public export` in CI so the canonical-link path stays exercised before more
live canonical examples exist.

## Reference examples

Use these entries to inspect different evidence shapes; read their current
manifest and retained assessments rather than relying on an old status summary:

- [ripgrep](repos/github.com/BurntSushi/ripgrep/): README command declarations
  and Cargo toolchain evidence
- [GitHub CLI](repos/github.com/cli/cli/): manifest inference, task-script tests,
  ownership, and a security-reporting URL
- [ries-rs](repos/github.com/maxwellsantoro/ries-rs/): accepted claim linked to
  upstream native metadata; the checked-in record remains an overlay
- [bat](repos/github.com/sharkdp/bat/) and [fd](repos/github.com/sharkdp/fd/):
  related Rust project shapes with different security evidence/absence

These are source-linked examples, not proof that every field is correct or that
maintainer acceptance itself published a canonical mirror.

## Operator entrypoint

Use [factual crawl automation](../docs/factual-crawl-automation.md) for scheduled
refresh, enablement variables, credentials, exact-head automatic landing,
telemetry, and failure recovery. Scheduled writeback honors explicit enablement;
only an explicitly requested local batch may opt in with
`--skip-automation-enabled-check`.

Writeback eligibility permits validated partial records; promotion to `verified`
requires the stricter fresh-inspection gate. Do not turn manual review into a
routine generated-record approval tier. Claim review remains a separate
[authority workflow](../docs/maintainer-claim-review-workflow.md).

## Local validation

Run:

```bash
cargo run -p dotrepo-cli -- validate-index
```

CI runs the same command in pull requests and in the primary-branch validation
workflow.

## Crawler seeding

Use the checked-in candidate catalog when you want deterministic imported-lane
batch output plus an audit report:

```bash
cargo run -p dotrepo-crawler -- seed \
  --targets-file index/tranche-two-targets.txt \
  --dry-run \
  --review-report-md /tmp/dotrepo-seed-review.md
```

The markdown report is advisory only. It does not change index validity, record
trust semantics, autonomous publication gates, or the manual contribution bar.

## Growth status

Generate current counts, ecosystem mix, incomplete-field queues, and record-age
reports rather than copying metrics into documentation. The high-signal and
capacity counts are advisory; they do not establish accuracy, freshness, or
consumer usefulness.

```bash
uv run python scripts/render_index_growth_status.py \
  --stale-after-days 30 \
  --max-stale-or-missing-record-rate 0.10 \
  --max-refresh-overdue-days 7
```

The [public freshness gate](../docs/public-freshness.md#profile-record-policy)
evaluates exported factual age independently at the current clock. Use the
[roadmap](../ROADMAP.md) to decide which improvement or growth work may start.

Use the core promotion report for read-only analysis of retained value-bound
assessments (it does not inspect upstream or authorize a new promotion):

```bash
cargo run -p dotrepo-cli -- promotion-report --index-root index --json
```

The JSON summary separates `eligibleCount` from `promotionCandidateCount`.
`eligibleCount` includes already verified records; `promotionCandidateCount`
counts eligible draft/imported/inferred records. Fresh crawler verification is
required to mint verified status; standalone `--apply` is disabled on this branch.
High-signal counts are advisory, not a release incentive.

## Growth tranche planning

Use the growth-tranche planner when preparing the next candidate catalog. It
accepts a grouped candidate file, such as
[`index/tranche-two-targets.txt`](tranche-two-targets.txt), removes repositories
that already have `index/repos/**/record.toml`, balances the remaining targets
by group in candidate-file order, and emits both crawler-ready targets and an
audit report:

```bash
uv run python scripts/plan_index_growth_tranche.py \
  --candidate-file /tmp/dotrepo-next-candidates.txt \
  --target-count 50 \
  --min-selected 50 \
  --output-targets /tmp/dotrepo-growth-targets.txt \
  --output-json /tmp/dotrepo-growth-plan.json \
  --output-md /tmp/dotrepo-growth-plan.md
```

Prepare `/tmp/dotrepo-next-candidates.txt` as one identity per line, with `#`
comments naming ecosystem groups. The completed tranche-two catalog is exhausted
and cannot satisfy a positive new-target floor. The active baseline intentionally
requests zero growth until new evidence-backed candidates and roadmap gates exist.

The emitted targets can feed `dotrepo-crawler seed --targets-file`. Planner
capacity fields are advisory; they do not establish valid published profiles,
accuracy, freshness, or consumer utility. The release gate reads its planning
policy from `scripts/fixtures/index_growth_tranche_baseline.json`.

### Repository identity migrations

`identity-migrations.json` records verified upstream renames/transfers. Each entry
retains the old and new identities, numeric GitHub repository ID, and check time.
The new identity is freshly crawled before the old overlay is removed. Old lookup
paths become misses; consumers can follow the upstream repository redirect and
retry the current identity. Crawler state does not resurrect removed identities.
