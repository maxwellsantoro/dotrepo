# October 4 structured metadata recapture

`identities.txt` replays the 32 identities from the existing independently
selected September structured metadata workload. Identity selection was frozen
before this capture. It is a repeated source check on a known cohort, not a new
independent holdout, command evaluation, or completed consumer-task measurement.

Each repository JSON retains the relevant GitHub API metadata and check time.
`workload.json` contains 123 exact-value assertions derived from those upstream
responses without reading dotrepo's asserted values. The capture records its
actual normalized identity-list digest rather than claiming a selection method
that the capture tool did not perform.

`prior-export-accuracy.json` and `.md` preserve the unfavorable results against
the September 21 export: 121 matches, two mismatches. The mismatches are git-bug's
changed description and Solace Agent Mesh's archive flag. The current index had
already corrected the archive flag. The description correction in this change
removes its obsolete assessment and supersedes verified authority; other source
inspection timestamps are preserved.

`current-index-accuracy.json` and `.md` evaluate the resulting current export
against the same frozen October 4 capture. An exact match to these API fields
does not establish command usefulness, abstention calibration, factual coverage
beyond this cohort, or independent consumer adoption.

Reproduce the current-index comparison after exporting the current index:

```bash
uv run python scripts/measure_public_factual_accuracy.py \
  --public-root /tmp/dotrepo-roadmap-final-public-gate/public \
  --workload benchmarks/head-to-head/upstream-2026-10-04/workload.json \
  --min-assertions 123 --min-repositories 32 --min-accuracy-rate 1 \
  --max-mismatch-rate 0 \
  --output-json /tmp/dotrepo-current-index-accuracy.json \
  --output-md /tmp/dotrepo-current-index-accuracy.md
```

Frozen September and October 3 evidence and benchmark results remain unchanged.
