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

## Evidence rubric

Reference-quality `evidence.md` files should make a record auditable without
forcing a consumer or operator to reverse-engineer where claims came from.

At minimum, every overlay evidence file should:
- state what was imported directly and name the upstream source
- state what was inferred and explain the reasoning path
- explain where `repo.build` came from, even when the answer is "inferred from project layout"
- explain where `repo.test` came from, even when the answer is "inferred from project layout"
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
is retained for reproducible first-tranche crawler runs. The active growth
candidate catalog is [`index/tranche-two-targets.txt`](tranche-two-targets.txt).
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

These index entries are useful reference examples for v0.1:
- [`github.com/BurntSushi/ripgrep`](repos/github.com/BurntSushi/ripgrep/) shows a trust-aware overlay with inferred build and test commands plus an intentional `unknown` security contact.
- [`github.com/cli/cli`](repos/github.com/cli/cli/) shows a heavily imported overlay with build, test, license, and security claims tied to specific upstream sources.
- [`github.com/maxwellsantoro/ries-rs`](repos/github.com/maxwellsantoro/ries-rs/) shows a reviewed Rust overlay with a live accepted maintainer-owned claim now linked to the upstream native `.repo`, so the public claim context derives `superseded` while the checked-in seed record remains overlay-only.
- [`github.com/sharkdp/bat`](repos/github.com/sharkdp/bat/) shows a curated Rust overlay with maintainer handles, imported development commands, and explicit security reporting evidence.
- [`github.com/sharkdp/fd`](repos/github.com/sharkdp/fd/) shows the same evidence standard on a second repository with similar project shape, so contributors can compare patterns across examples.

These entries should be strong enough to serve as model contributions for future
overlay submissions, not just as structurally valid records.

## Local validation

Run:

```bash
cargo run -p dotrepo-cli -- validate-index
```

CI runs the same command in pull requests and in the primary-branch validation
workflow.

## Crawler seeding

Use the checked-in tranche list when you want deterministic imported-lane batch
output plus an audit report:

```bash
cargo run -p dotrepo-crawler -- seed \
  --targets-file index/tranche-two-targets.txt \
  --dry-run \
  --review-report-md /tmp/dotrepo-seed-review.md
```

The markdown report is advisory only. It does not change index validity, record
trust semantics, autonomous publication gates, or the manual contribution bar.

## Growth status

Use the growth-status renderer when you need a quick read on record-level
high-signal progress, active-tranche capacity, tranche coverage, language mix,
claim examples, high-signal lift candidates, and which lower-confidence records
should be hardened next:

```bash
uv run python scripts/render_index_growth_status.py \
  --milestone-high-signal-target 500
```

The scheduled seed and refresh review workflows include this same readout in
their GitHub step summaries and uploaded artifacts. The active-tranche capacity
line is an upper bound: missing tranche targets still need to be crawled,
validated, exported, and measured before they count toward public-profile
coverage. The high-signal lift queue is also advisory; it highlights records
with medium/high confidence plus build, test, and security signals that still
need the normal validation and promotion path before they can increase the
high-signal count. The record-level potential line shows how far the checked-in
index could move if those candidates pass that path.

Use the core promotion report when you need the authoritative auto-promotion
view:

```bash
cargo run -p dotrepo-cli -- promotion-report --index-root index --json
```

The JSON summary separates `eligibleCount` from `promotionCandidateCount`.
`eligibleCount` includes already verified records; `promotionCandidateCount`
counts only eligible draft/imported/inferred records that could actually raise
the high-signal profile count if promoted through the verified auto-publish path.

## Growth tranche planning

Use the growth-tranche planner when moving from the first checked-in tranche to
larger candidate sets. It accepts a grouped candidate file, such as
[`index/tranche-two-targets.txt`](tranche-two-targets.txt), removes repositories
that already have `index/repos/**/record.toml`, balances the remaining targets
by group in candidate-file order, and emits both crawler-ready targets and an
audit report:

```bash
uv run python scripts/plan_index_growth_tranche.py \
  --candidate-file index/tranche-two-targets.txt \
  --target-count 100 \
  --min-selected 100 \
  --current-high-signal 107 \
  --milestone-high-signal-target 500 \
  --min-planned-high-signal-capacity 207 \
  --output-targets /tmp/dotrepo-growth-targets.txt \
  --output-json /tmp/dotrepo-growth-plan.json \
  --output-md /tmp/dotrepo-growth-plan.md
```

The emitted targets can be passed to `dotrepo-crawler seed --targets-file`.
Planning a tranche is only an operational input; its Milestone 2 capacity
section reports current high-signal coverage plus selected targets as an upper
bound, not as completed coverage. The Milestone 2 gate is still the exported
profile coverage report, which counts valid high-signal profiles after records
are crawled, validated, exported, and measured.
The scheduled seed-review workflows now run this planner first and crawl the
planned target file, so already-indexed candidates do not consume growth slots.
Those workflows read the checked-in profile-coverage and tranche baselines and
pass the same Milestone 2 capacity fields to the planner that the canonical
release gate uses.
