# Bounded factual checkpoint — 2026-10-06

The two historically affected command records were statically reinspected at their retained source revisions. This closes the bounded command-source checkpoint; it does not close population quality or ongoing factual freshness.

| Identity and pinned revision | Field | Disposition |
| --- | --- | --- |
| `github.com/ggml-org/llama.cpp` at `05f2dcfdba3879c55f735efa0f124b1a56f7ed11` | build | Keep scalar unset. The Makefile errors. Retain the documented CPU CMake build as a candidate with prior configuration and tool requirements. |
| same | test | Remove inferred `python -m pytest`; its development dependency does not declare a repository test instruction. |
| `github.com/etcd-io/etcd` at `f094b9834a5aa0ef748b91509b824e324dd65700` | build | Retain exact `make build` wrapper with root context and documented development preparation. |
| same | test | Confirm `make test-unit` correction, with root context and preparation; compilation-only stress example remains excluded. |

The old `ggerganov/llama.cpp` identity is absent from the current index; the inspected record uses `ggml-org/llama.cpp`. No obsolete identity was recreated.

Record ages/statuses and unrelated facts/assessments are unchanged. New command/context evidence is checked at the inspection time and cannot make the whole record young. The real Rust exporter consequently drops those newer assessments; the actual reference consumer withholds all four instruction requests. A coherent full-record crawl is required before contextual acceptance. No upstream command was executed, and no record was promoted.

The current exported-record freshness gate passes: 616 fresh, no stale/unknown records, oldest age 19 days, no overdue repositories. The reproducible seed `20261006` draws 20 risk-weighted cases; those remain uninspected by this bounded packet. The full documentation audit flags 419 records for source inspection. Flags and completeness budgets are not factual correctness or consumer usefulness measurements.

PR [#135](https://github.com/maxwellsantoro/dotrepo/pull/135) remains open at `e960c0f979f449c2b1a6001ca734635b8df01b53`, with zero exact-head check runs observed. Isolating that exact head through `git archive` and using the current CLI yields valid index/freshness (613 fresh, oldest 19 days) and a strict telemetry pass (34 checks). Its branch parent is `fa830e8ebb1b9bb825e08755f7da2c6c34381dbf`; the API-reported base is `3c3ccd725a20cdbaf1f6502147dfda2e528ec74a`, while inspected main is `dde2238e951c3912de1bc7cdba05686bef90818a`. Thus this does not establish current writeback eligibility: the expected-base/non-force fast-forward contract and required exact-head CI/public gate are unsatisfied. Regenerate the bounded batch against current main with fresh inspection and current policy; do not relabel retained timestamps or bypass landing safeguards. This packet did not edit or merge the PR.

Sources, exact values/contexts, hashes, timestamps, queue details and check receipts are retained in [the machine-readable receipt](roadmap-factual-checkpoint-2026-10-06.json). Full record recrawls, the risk-weighted audit dispositions and cross-ecosystem error/abstention measurement remain F2 work.


Integration corrected an assessment-binding defect: the initial Python comparison normalized an absent `component` to `null`, while the core serializer omits that key. Every newly assessed field across both packets was queried through the actual Rust CLI; 11 bindings were corrected. Real record ages/statuses remain unchanged. In a disposable copy where only record timestamps match the new assessments, the actual exporter retains all 39 assessments and the actual consumer selects the 11 supported contextual instructions. These are serialization/selection controls, not upstream task execution. Details are in the machine-readable receipt.
