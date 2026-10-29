# Go-01 oracle amendment 1: native hierarchy consistency

This append-only amendment fixes the two findings and three accepted malformed
synthetic traces retained by the independent before-review. The original oracle,
16 source-preparation artifacts, original freeze and before-review bytes remain
unchanged. `BEFORE.json` binds the original oracle/run results and the frozen
independent review before any amendment control ran.

The successor keeps the exact source revision, whole wrapper command, environment
contract and unaccepted 380-entry exclusion proposal. Native collection remains
missing. No cache preparation, package/source fetch, Docker, native test,
model/provider call or VM change occurred.

## Corrected checks

- A nested run requires its existing slash-delimited ancestors to remain live.
  A child cannot begin after an ancestor's terminal event.
- A parent cannot emit pass, fail or skip while an observed descendant remains
  unfinished. Descendant counts track observed runs and terminal events; they
  infer no unobserved children and avoid scanning all prior events per terminal.
- A failed descendant requires failed ancestors. A passing or skipped ancestor
  cannot coexist with that failure. Complete terminal assertion failures remain
  eligible candidate outcomes when all original coverage/process checks pass;
  `testsPassed=false` is retained separately.

The primary source bound by the before-review shows Go `testing.common.Fail`
recursively failing its parent and the parent waiting for subtests before
completion. `parallel-source-binding.json` additionally binds existing exact
common-image `testing.Parallel` and test2json source to support the synthetic
pause/continue controls. The source was read as data from an already retained
image export; no toolchain code was executed.

The existing slash-delimited identity contract is retained. Prefix lookalikes
such as `child` and `childish` are separate. Source-derived dynamic identities
and any literal-slash naming ambiguity remain part of the missing native
manifest/hierarchy adjudication; this amendment does not claim to reconstruct
arbitrary Go parent relationships from names.

## Controls and preserved limits

`controls-final.json` records all 60 original synthetic controls passing against
the final successor. `hierarchy-results.json` records 18 additional controls:
the exact three frozen malformed traces reproduce acceptance in the old oracle
and rejection in the successor; valid sequential/parallel siblings, prefix
collisions and complete deep assertion failures pass; malformed descendant
ordering and inconsistent ancestor outcomes fail. Every synthetic positive
still reports `taskOutcomeObserved=false`.

The excluded-child-only example remains a declared manifest/coverage limitation.
An asserted complete top-level manifest cannot prove unobserved intended children.
No generic requirement that every parent have an active child was added. Missing
native collection, unaccepted policy, dynamic fixture/config/seed conditions,
capability/setup questions and ignored-hook equivalence remain unresolved exactly
as before. No new exclusions may be minted from future observed failures.

`controls.json` is the preceding successful 60-control snapshot; the final code
uses counters rather than repeated historical descendant scans. The original
packet's source-bound exclusion content is read from its original location and
hash-checked by the successor; no duplicate policy or changed scope was created.

Reproduce synthetic controls into fresh output paths:

```sh
uv run --offline --no-sync python benchmarks/head-to-head/f05-go01-oracle-preparation-20261029/amendment-1/controls.py --output /tmp/dotrepo-go01-amendment-controls-unique.json
uv run ruff check --no-cache benchmarks/head-to-head/f05-go01-oracle-preparation-20261029/amendment-1
uv run ruff format --check --no-cache benchmarks/head-to-head/f05-go01-oracle-preparation-20261029/amendment-1
```

`hierarchy_controls.py` writes its retained output exclusively. The successor
oracle CLI has the original arguments, with this directory's `oracle.py` path;
using it to score retained native evidence still requires the original external
collection, acceptance, provenance and setup gates. This is a bounded synthetic
correction, not native qualification or consumer evidence.
