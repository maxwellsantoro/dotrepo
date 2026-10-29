# E1 context adjudication input repair — known development

This packet repairs the missing whole-tuple/source-body input to the existing
bounded adjudication ladder. It does not establish instruction completeness,
independent qualification, execution success or consumer benefit. Development
identities are declared in `development-identities.json`; only the previously
retained Keras testdata and owned synthetic controls were exercised. No new
extractor/grammar rule, fingerprint confidence allowlist, dependency, manifest or
public protocol/version was introduced. Worktree base is `8a8da06d` on
`codex/e1-context-adjudication`; no worker commit, push or branch switch occurred.

The new focused core module builds separate contextual requests for existing RFC
0021 `BuildTestCandidate` tuples. An exact field/tuple/generation identity binds
bounded source passages, whole-file SHA256, exact UTF-8 passage bytes, line spans,
body SHA256 and citation IDs. Repeated files with distinct spans are supported.
The provider must select an existing exact tuple, its source and every retained
citation exactly once, or abstain. Command, cwd, scope, component, prerequisites,
source, tuple, timestamp and citation edits cannot select a changed value. Low
confidence and abstention remain Unresolved, never high-confidence absence.

**The explicit caller/importer admitted-input inventory is authority for body
reads; containment is additional validation.** A path must exactly occur in
`ImportPlan.imported_sources` before it can be read for adjudication. Naming an
arbitrary contained `.env`/private file in a candidate is insufficient. The shared
regular-file/no-symlink/bounded reader still applies. A negative control names an
unadmitted `.env` containing a marker and verifies that no content enters the
request and selection is refused. Ancestor/leaf links, traversal, missing,
changed, malformed or oversized declared sources also refuse selection. Exact
source bytes, admitted inventory, tuple and generation time are reobserved after
a provider returns; capture itself is not a filesystem lock against active actors.

The source reader remains capped at 2 MiB per file. Context requests consider at
most 8 candidates, with 16 spans, 8 KiB per retained span and 64 KiB retained source
body per request. Tuple JSON is capped at 32 KiB, attachment JSON at 128 KiB;
serialized evidence shedding targets 96 KiB, with explicit omissions if metadata
or passages exceed it. Required omitted bodies prevent selection. Additional
upstream files and prerequisite closure remain explicitly unknown; a partial
materialization never proves upstream absence. Current import inputs do not prove
commit pinning (crawler fetches branch paths), so `sourceRevision` is null with an
explicit unknown reason. No branch-head SHA is misrepresented as a source revision.

Scalar request ordering and shared per-record/provider-call budgets are preserved:
context requests are appended after scalar work. A 32-candidate/large-body control
with a one-call budget observes only the unresolved scalar build request; no
additional context call occurs. Failed attempts still consume the existing shared
cap. Context selection never rewrites `repo.build`, `repo.test`, or any tuple,
never blends conflicts, and cannot mint High or record authority/status. Existing
higher-confidence fields are preserved. Old scalar JSON omits the new optional
context evidence/citations, and old responses deserialize with empty citations.
Rust literal callers have the necessary new optional/default-field initializers.

Crawler HTTP serialization transports the typed evidence/citations. The sidecar
labels source as untrusted data, preserves exact tuple values, constrains response
schema/citations and refuses mutated or incomplete selections, retaining measured
tokens for unusable responses. Model/provider assignments and policy settings are
unchanged. The known Keras request retains eight spans (7,318 source-body bytes),
including requirements; `known-keras-request.json` is actual owned import output.
Its sidecar control is an owned synthetic response, not a model answer or semantic
completeness finding. Keras baseline scalar extraction is preserved.

## Focused checks

Final source: 13 new context unit tests, 14 existing adjudication/safety integration
tests, 10 existing escalation tests, one crawler wire test, and all 24 focused
sidecar tests passed. The latter include an owned loopback server with provider
calls mocked. Core/crawler all-target Clippy (`-D warnings`), Cargo fmt, and focused
Ruff check/format passed. Cargo used `--offline --locked` and a separate
`/tmp/dotrepo-e1-context-adjudication-target`; Python used uv. Exact commands,
logs and superseded successful receipts are retained in `focused-checks.json`.
Initial implementation/test assumptions are retained in
`development-observations.json`. No upstream, native task, external network,
paid provider/model or container execution occurred. No full gates were run by
this worker; the coordinator owns combined integration gates and review.

## Remaining gates and limits

Mechanical hashes/citations and Medium selection do not settle whether every
prerequisite, platform, hidden setup or task scope is supported. Existing Keras
source-completeness questions and Compose/Zellij dispositions are unchanged.
Independent implementation review and separate source-completeness assessment
precede any higher acceptance. No held-out corpus or F05 data was used for tuning.

Existing budget owners are unchanged: the core `model_ladder.rs` attempt counter,
crawler `INDEX_MAX_ADJUDICATION_CALLS`, and batch
`run_autonomous_index_batch.py:crawl_env_for_remaining_budget` clamp per-record
calls to remaining batch calls. `openrouter_request_policy.py:build_completion_body`
bounds completion tokens and configured per-million provider prices. It has no
pre-call prompt-token or total-dollar estimate/cap; larger evidence input is
byte-bounded, not a new monetary guarantee. Actual provider costs remain unknown;
this worker launched zero external calls. Live enabling needs operator budget
review in addition to the independent source/implementation gates.
