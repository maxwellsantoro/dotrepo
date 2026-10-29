# Remaining E1 slice evaluation and combined observations

All **24 frozen tasks across twelve repositories** now have observed extraction
and contextual-consumer outcomes at implementation commit
`f79d05a27b31f281ab04a23cd269e927a25833e4`. This packet adds eighteen tasks
from nine repositories to the unchanged six-task Rust result. Observation
coverage is complete; source gold remains unresolved for eight tasks and the
full qualification gate has **not** passed.

The [prospective execution freeze](execution-freeze.json) was retained before
any new import. It binds cohort manifest
`8d44598ba00725fac046ca8da50fdbc1252d2440eb6ec04d690a1129cecb0c63`, the
same 503 evaluated source/dependency/consumer hashes and identical CLI binary
used by the Rust packet, this evaluator, the immutable Rust helper/scorer, the
consumer policy/scoring method, runtime, original Rust results, and four
[source-independent scoring controls](scorer-controls.json). All four source
slice freezes, 219 artifact bindings and twenty selection-input bindings were
verified before and throughout execution.

## Observations

All nine additional imports and all three public exports succeeded. Every
requested profile existed at its ordinary exported route, including mixed-case
repository names. None of the eighteen contextual-consumer requests accepted
an instruction; each returned `no-assessed-contextual-instruction`. No complete
test context or contextual test candidate was recovered. Scalar commands, when
present, remain separate from complete instruction recovery and consumer acceptance.

| Ecosystem | Tasks | Consumer accepts | Supported misses | Correct abstentions | Unresolved gold |
| --- | ---: | ---: | ---: | ---: | ---: |
| Rust, retained unchanged | 6 | 0 | 3 | 1 | 2 |
| Python | 6 | 0 | 2 | 0 | 4 |
| JavaScript/TypeScript | 6 | 0 | 4 | 1 | 1 |
| Go | 6 | 0 | 5 | 0 | 1 |
| Combined | 24 | 0 | 14 | 2 | 8 |

| Task scope | Tasks | Supported misses | Correct abstentions | Unresolved gold |
| --- | ---: | ---: | ---: | ---: |
| Repository | 12 | 9 | 1 | 2 |
| Component | 12 | 5 | 1 | 6 |

The fourteen supported gold cases with no accepted contextual instruction are
**supported misses**. Missing assessments do not make those correct abstentions.
The eight unresolved cases remain in the task denominator as unresolved gold.
There were no incorrectly accepted instructions because no instruction was
accepted; this does not establish precision or a population safety guarantee.
Actual fallback work and final task completion were not performed or measured.

## Retained evidence

- [Combined 24-task results](run-001/combined-results.json) join the original
  hash-bound Rust observations without changing them.
- [Remaining eighteen-task results](run-001/remaining-results.json) retain every
  request, extracted scalar/candidates/context, consumer selection and gold
  disposition from this run.
- [Python](run-001/python/results.json),
  [JavaScript/TypeScript](run-001/typescript/results.json), and
  [Go](run-001/go/results.json) each retain a six-task report, source
  materialization inventory, consumer observations saved before the gold join,
  import stdout/stderr/receipts and unmodified records/evidence, and the actual
  public export including profiles and snapshot/meta payloads.
- [The combined artifact inventory](run-001/artifact-hashes.json) binds all 189
  retained run files other than itself. Each slice also has its own inventory
  binding 61 files.

Only source paths bound by the corresponding slice freeze were copied into
new temporary repository roots. These bounded materializations are not full
checkouts: missing unretained files or Git metadata can limit extraction. The
operator did not fetch additional sources, repair records, synthesize assessments,
execute upstream commands, or call a model. The source-gold curator received no
extraction outputs. These exposed cases are now known workloads for later
implementation iterations, not fresh holdouts for an improved extractor.

## Reproduction

The initial command froze all three remaining slices before execution; existing
freeze/control files intentionally cannot be overwritten:

```bash
uv run python benchmarks/head-to-head/e1-qualification-20261029/evaluation-remaining/evaluate.py \
  freeze --slices python typescript go
```

From the frozen checkout with the frozen binary and runtime, verify inputs and
choose a new result directory:

```bash
uv run python benchmarks/head-to-head/e1-qualification-20261029/evaluation-remaining/evaluate.py verify
uv run python benchmarks/head-to-head/e1-qualification-20261029/evaluation-remaining/evaluate.py \
  run --out /tmp/dotrepo-e1-remaining-new-run
```

Exact commands, timestamps and exit statuses are retained in the import/export
receipts. CLI import timestamps are generated during each run; a replay may have
different record/profile bytes. Export timestamps are fixed to the execution
freeze. Changed code, source, binary, policy, or scorer requires a new experiment
contract rather than rewriting this result. This is extraction/consumer-policy
measurement, not upstream execution evidence, independent participation, an
agent task campaign, or demonstrated consumer benefit.
