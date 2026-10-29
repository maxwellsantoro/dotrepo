# Frozen Rust slice extraction evaluation

This is a **six-task partial qualification result out of the planned 24 tasks**.
It does not close the full E1 qualification gate, demonstrate upstream execution,
or measure an agent's task completion, effort savings or consumer benefit.

The evaluated implementation is commit
`f79d05a27b31f281ab04a23cd269e927a25833e4`. Before importing, the retained
[execution freeze](execution-freeze.json) bound the evaluator/scorer script,
prebuilt CLI bytes, 503 evaluated source/dependency/consumer files, the consumer
policy and scoring method, and the upstream source-gold freeze
`de16bbd397558679033140543e24cf7ad45d0804552b2a0c2efe5356dd182205`.
All 50 source-gold artifacts and five selection inputs were verified unchanged.
The binary binding records the coordinator's build-revision attestation; it is
not a reproducible-build proof.

## Observations

All three overlay imports and the public export succeeded. The imports emitted
`cargo test --workspace` as a scalar for each repository, with no test context
and no contextual test candidate. None of these scalar values is counted as a
complete applicable instruction. The existing reference contextual consumer
accepted no instruction for any of the six requested tasks. Each response gave
`no-assessed-contextual-instruction` as its fallback reason.

| Scope | Tasks | Complete recovered contexts | Consumer accepts | Supported misses | Correct abstentions | Unresolved gold |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Repository | 3 | 0 | 0 | 2 | 0 | 1 |
| Component | 3 | 0 | 0 | 1 | 1 | 1 |
| Total | 6 | 0 | 0 | 3 | 1 | 2 |

The three supported source-gold tasks are **supported misses**. Missing public
assessments do not turn those into correct abstentions. The two tasks whose
setup evidence was unresolved remain unresolved; their outcomes are retained,
not converted into errors or correct abstentions. No incorrectly accepted
instruction was observed, because no instruction was accepted.

[Results](run-001/results.json) retain every task request, raw extracted
scalar/candidates/context, consumer decision, profile hash and post-selection
gold disposition. [Import receipts and original records](run-001/imports/)
retain stdout, stderr and the CLI's unmodified `record.toml`/`evidence.md`.
[The actual public export](run-001/public/) retains profiles, snapshot/meta and
other ordinary exporter payloads. [Materialization](run-001/materialization.json)
lists exactly which source bytes were available to each import. The
[output inventory](run-001/artifact-hashes.json) binds every retained run artifact.

## Boundary and reproduction

Only the retained frozen source files were copied into fresh temporary repository
roots. These are bounded source materializations, **not full checkouts**: missing
unretained files and Git metadata can limit extraction. The temporary roots and
index were discarded after retaining the output. The evaluator never repaired a
record, synthesized field assessments or executed an upstream command.

The consumer received task scope/component constraints, without gold commands or
prerequisites. All selections completed before scoring joined the alternatives.
The source-gold curator received no extraction output. These exposed cases are now
known workloads for future iterations; rerunning an improved extractor against
them would not supply a fresh generalization test.

The initial freeze was created with the following command, before the first
import. It intentionally refuses to overwrite the existing freeze:

```bash
uv run python benchmarks/head-to-head/e1-qualification-20261029/evaluation-rust/evaluate.py freeze
```

Verify current inputs, then choose a new output directory to reproduce the run:

```bash
uv run python benchmarks/head-to-head/e1-qualification-20261029/evaluation-rust/evaluate.py verify
uv run python benchmarks/head-to-head/e1-qualification-20261029/evaluation-rust/evaluate.py run \
  --out /tmp/dotrepo-e1-rust-new-run
```

The evaluator requires the frozen checkout, binary and runtime. If any changes,
create a new experiment/run contract rather than updating this packet. The CLI
import uses its actual timestamp, so replayed record/profile bytes may differ;
the exporter uses the frozen deterministic timestamps. Retained exact command
arguments and timings are in each receipt. Four source-independent synthetic
[scoring controls](scorer-controls.json) checked supported-miss, required
abstention, unresolved gold and absence of complete context before evaluation.
