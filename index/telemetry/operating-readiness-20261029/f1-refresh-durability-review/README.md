# F1 withdrawal durability — read-only source review

At source HEAD `91643102c6083fda66827f68e43a06e7cdc8cec8`, the deterministic
importer can repopulate all four scalar values withdrawn for IBM/fp-go and
 gomodule/redigo in PR #185. This is a source control-flow proof, **not an executed
CLI/crawler replay**. No existing debug binary was treated as matching this HEAD;
no Cargo build, upstream execution, new fetch, index mutation or Rust edit ran.

| Frozen identity/revision | Field and value the current path selects | Why the withdrawal still matters |
| --- | --- | --- |
| IBM/fp-go `42e25c64425e2291bd5b281aa852b7a790526204` | `repo.build = go build ./...` | Root-module build may work, but a repository-default aggregate is not source-established. |
| Same | `repo.test = go test ./...` | Root wildcard does not represent the separately declared v2/gen-v2 module jobs. |
| gomodule/redigo `57c8b99ccb90c3401bec6e09289081e8b78b3bde` | `repo.build = go build ./...` | Installation guidance and release workflow do not establish this repository-default build. This is insufficient evidence, not observed failure. |
| Same | `repo.test = go test ./...` | CI explicitly installs Redis, then runs `go test -race ./...`; the fallback discards setup and the source flag. |

`infer_go_module_commands` emits both defaults from any root `module` declaration.
For IBM, `infer_workflow_commands` already refuses the entire workflow because it
contains `cd v2`/`cd gen/v2`, but this refusal does not block the lower metadata
fallback. For Redigo, workflow extraction accepts `go test -race ./...` without
carrying its Redis setup; policy then deliberately replaces flagged Go workflow
commands with the bare `go.mod` default. The existing unit test
`workflow_go_selectors_do_not_outrank_module_defaults` locks that normalization
behavior. These paths are bound with exact source bytes and line passages in
[source-bindings.json](source-bindings.json).

All four selections score **medium-confidence inferred**, not high confidence.
That prevents verified auto-promotion, but does not delete the scalar values from
a newly built import plan. This review does not assert that a scheduled refresh
actually wrote or published them; scheduling/writeback/publication gates were not
executed here.

The current records do retain individual source-bound unresolved/null inspection
assessments, and the historical correction packet retains the rejected old
values. They are durable records of the audit, but **not enforceable per-value
tombstones**. Refresh constructs a new import plan from materialized source; it
uses the prior record for native/reviewed/canonical protection and record-level
downgrade reporting. It neither passes prior field assessments into the importer
nor reapplies them afterward. `retain_field_evidence` replaces assessments from
fresh scores. Its attachment-preservation check reads the new plan, not the prior
record. `valueJson=null` binds absence; it does not identify every future rejected
candidate. The record downgrade guard returns `preserved=false` and does not
restore prior fields. Both corrected records are inferred overlays, so the
maintainer/reviewed-record refusal does not protect these four fields.

## Proposed next packet

[findings.json](findings.json) separates narrow guards from wider policy changes:

1. A module-scope guard can stop IBM metadata fallback when source establishes
   multiple owned modules with separately scoped Go CI. Keep unqualified candidate
   evidence and unresolved state. Do not invent a joined all-module command or
   trigger merely because an unrelated example module exists. Current crawler and
   importer inputs only acquire/read root `go.mod`; a manifest-aware guard needs
   explicitly bounded source discovery/input ownership, or an honest workflow-scope
   uncertainty guard. The retained module manifests are fixture evidence, not
   proof the present crawler always sees them.
2. A job-scoped setup/variant guard can stop Redigo's test fallback, preserving
   Redis and `-race` as attributed evidence. Removing flag normalization alone
   would leave an incomplete flagged scalar. Do not suppress tests just because an
   unrelated lint/release job sets up Redis. Existing workflow extraction is
   line-based, so preserving job scope is real implementation work.
3. Redigo's **build** withdrawal cannot be justified by its test Redis prerequisite.
   Durable enforcement of all four individual withdrawals needs an explicit
   value/source-bound negative-assessment decision, or a separately reviewed wider
   Go scalar-default policy. Existing freeform reasons/audit locators must not
   become executable rejection rules. A negative-assessment design must identify
   the exact rejected value and source closure and define fresh override behavior;
   prior null alone cannot become a permanent universal veto.
4. Globally removing every Go metadata default is a broader acceptance/coverage
   decision. It is not silently included in the narrow scope/setup proposal.

[fixture-contracts.json](fixture-contracts.json) freezes nine proposed positive and
negative contracts. Two proposed fixture directories copy exact retained IBM and
Redigo inputs, including original workflows and module/setup evidence. They have
not been added to the importer fixture pack or tested as Rust fixtures. Synthetic
positive controls preserve metadata-only behavior under the narrow proposal,
source-declared root defaults and unrelated example/setup cases. Optional refresh
controls distinguish an exact prior withdrawal from new source-grounded evidence.
No existing fixture expectations were changed.

The minimum narrow scope/setup work protects IBM's two fields and Redigo's test
field. It does **not** claim to solve Redigo's build withdrawal through an unrelated
runtime prerequisite. The coordinator must choose the remaining durability policy
before assigning implementation and acceptance tests.

Focused checks verify that all 15 copied upstream sources match the original F1
freeze, all 12 Rust source files match the recorded HEAD, all four old withdrawal
values/dispositions are retained, and every bound passage is in range. No dynamic
reproduction or acceptance/generalization/consumer claim is made.

[checks.json](checks.json) and [FREEZE.json](FREEZE.json) bind this review. Shared
Rust, current index records and earlier frozen evidence remain unchanged.
