# Requirement-assessment development example — 2026-10-30

This bounded increment separates metadata discovery from source-backed
qualification of shortlisted repository components. It preserves both
Discovery-100 runs and their negative quality-per-token result.

The example uses MarkItDown at
`7482c092d9c0074a89803c9fdb63a969e7fe17fc`, component
`packages/markitdown`. These are already-retained sources from the prior
100-repository packet; no new origin requests were made.

This is the user's illustrative document-conversion scenario, selected for
development. It is not a fresh independently chosen task, a consumer-agent
comparison, or evidence of saved investigation effort.

## Files

- `demo-001/assessment.json`: three proposed source assessments, exact scope
  and source references. Two describe publisher-declared DOCX/PPTX conversion;
  one derives exclusion of Python 3.9 from the declared interpreter range.
- `source-review.json` and `independent-review.txt`: independent review of
  the source meanings and bounded implementation.
- `demo-001/store.sqlite`: disposable development store with retained source,
  raw assessment/review inputs and compiled records. The older frozen databases
  are unchanged.
- `demo-001/mcp-input.jsonl`, `mcp-output.jsonl` and `result.json`:
  actual metadata find, describe and qualify exchange.
- `demo-001/REPORT.json`: measured response sizes and whole-process timing,
  with explicit limits on what the demonstration establishes.
- `CHECKS.json`: integrated validation and cost limitations.

## Replay

From the repository root, after the locked development environment and first-party
Rust CLI are available:

```bash
uv run --offline --no-sync python benchmarks/head-to-head/repodigest-discovery100-comparison-20261030/pack_evidence.py unpack
uv run --offline --no-sync python benchmarks/head-to-head/repodigest-requirements-20261030/demo.py replay --output benchmarks/head-to-head/repodigest-requirements-20261030/demo-001
```

Replay requires the exact reviewed assessment bytes and current source/reader
policies. The retained result remains historical if those policies later change;
write a separate output for a new run. The `prepare` operation can create a new
output from the retained snapshot but does not create a review approval.

The intended results are supported for advertised DOCX and PPTX conversion,
unknown for absence of a LibreOffice requirement, and contradicted for declared
Python 3.9 compatibility. No upstream software is run and no execution authority
is granted.

## Evaluation still needed

A real user selection task should be frozen independently of the repository
descriptions. Both comparison arms need the same competent metadata search,
source access and final-choice standard. Only the treatment receives previously
compiled evidence. Count total follow-up reading, model/tool use, origin
requests/bytes, verification, and amortized assessment/maintenance costs.
Review complete final choices independently. No new paid consumer sessions or
execution study is launched by this packet.

See [the experimental guide](../../../docs/experimental-repodigest-requirements.md)
for admission trust, response bounds and invalidation.
