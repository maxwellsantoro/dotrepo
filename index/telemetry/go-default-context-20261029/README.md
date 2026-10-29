# Go default context guard — development packet

This packet prevents three known unsafe scalar reintroductions from retained
F1 sources: IBM/fp-go build and test, and gomodule/redigo test. It is a
fixture-backed development regression result. It is neither independent
qualification nor consumer-benefit evidence. No upstream code, provider, index
refresh, or network acquisition was executed.

The source baseline is `d76581560e88e92d9a0298c2c7fc94e28c44542d`; the branch
metadata advanced to tree-identical `4b0d769d424118d063c0fffbb793c422edb88478`
during development. Exact implementation and fixture bytes are bound in
`implementation-bindings.json`. Original source URLs, revisions and hashes are
in `before-and-sources.json`; the earlier source-only durability review remains
unchanged.

## Changed behavior

The importer examines only acquired root workflow files. An observed Go
build/test under a nonroot working directory, `cd`, or `go -C` leaves repository
coverage unresolved, so conventional Go workflow/module defaults cannot fill
either scalar. This does not require unseen nested manifests. IBM's exact
workflow explicitly runs root, `v2`, and `gen/v2` tests; root metadata alone
cannot establish complete repository scope.

A job containing a root Go test and an explicit external-service prerequisite
withholds the inferred test scalar. The screen recognizes job services maps,
selected service setup action names, and bounded Redis server/install commands.
Redigo's exact job uses `shogo82148/actions-setup-redis@v1` with a Redis version
matrix before `go test -race ./...`. Normalizing that test to `go test ./...`
can no longer discard this observed setup.

The original attributed command candidates remain available for provenance and
unresolved scoring. A separate in-memory `blocked_scalar_fields` signal blocks
those repo.build/repo.test adjudication requests through deterministic,
configured model, and fallback tiers. Policy does not parse generated notes.
The blocked fields remain `Unresolved`, not verified absence. An independently
eligible explicit maintainer declaration can still select a scalar and leaves
that field unblocked. No manifest or protocol format changed.

## Fixtures and observed outcomes

| Fixture | Build | Test | Purpose |
| --- | --- | --- | --- |
| f1-go-multimodule-context | withheld | withheld | Exact IBM root inputs and workflow, without nested manifests |
| f1-go-service-context | go build ./... | withheld | Exact Redigo inputs; build policy intentionally unchanged |
| f1-go-declared-context | go build ./... | go test ./... | Explicit CONTRIBUTING declarations survive both workflow guards |
| f1-go-unrelated-service-context | go build ./... | go test ./... | Redis in another job does not invalidate the test job |
| f1-go-example-module-context | go build ./... | go test ./... | Unrelated example manifest/non-Go directory work is not a scope trigger |
| f1-go-services-block-context | go build ./... | withheld | Explicit same-job service map remains required context |

The synthetic controls are labeled by their fixtures. They are not upstream
facts. `fixture-plans.json` retains exact native and overlay plans. The proposed
expectation entries and append-only patch are supplied for the coordinator-owned
`expectations.json`; this worker did not modify that shared file.

`escalation-controls.json` retains six actual escalation runs for the three
blocked fixtures, with model-call budgets 0 and 2. Both deterministic and model
request construction preserve the block, no fake-provider invocation occurs,
and original candidates remain. A separate control verifies an unblocked build
remains adjudication-eligible when its assessment is suspect. Existing model
ladder tests continue to pass without real model calls.

## Focused checks

- Final Go context module: 12 tests passed, including six full importer fixtures,
  bounded escalation/refusal controls, explicit declarations, independent jobs,
  workflow/job/step directory defaults, Go -C, comments, service forms, and
  unrelated ecosystems.
- Commands/context suite: 63 tests passed before the final additional unblocked
  request assertion; the final Go module run covers the changed test body.
- Existing escalation suite: 10 tests passed; importer facade: 42 tests passed.
- Existing import quality gate: 2 tests passed. New expectations await the
  coordinator's append and combined gate.
- `cargo clippy -p dotrepo-core --lib -- -D warnings` passed; owned Rust formatting
  and diff whitespace checks passed.

Raw logs, including failed attempts, are retained under `checks/` and indexed by
`checks.json`. The initial guard control failed on list-leading
`- working-directory`; that defect was fixed and rerun. The `import::fields`
filter selected zero tests and is not reported as coverage. No full workspace
or release gate was run by this worker.

## Limits and remaining decisions

This is a bounded indentation/run-command screen for the observed workflow
patterns, not a YAML interpreter, shell evaluator, general prerequisite-closure
proof, or execution validator. It does not resolve reusable workflow calls,
anchors, arbitrary shell programs, every external service installation, every
conditional, or future upstream changes. A refusal can be conservative; an
untriggered guard does not establish complete prerequisites or applicability.
Explicit maintainer candidate handling and unrelated conventional Go defaults
retain the existing importer policy.

Redigo's build scalar remains inferred from go.mod. Its broader default-evidence
question is deliberately unresolved here. The packet introduces no durable
index tombstone and does not mutate the earlier withdrawn records: it prevents
these three reintroductions when the guarded source is present during fresh
import and ordinary adjudication. This is not a proof for undisclosed sources,
manual plan mutation, or direct invocation of lower-level adjudication helpers
with fabricated requests. Independent review and the coordinator's integrated
fixture/workspace gates remain required before landing.
