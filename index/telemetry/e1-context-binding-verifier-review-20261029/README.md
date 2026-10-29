# Independent mechanical source-binding review

The linked verifier and shared wiring passed this bounded independent review.
There is no blocking finding. This reviewer is separate from the verifier author
but has prior F-05/E1 project and result context. This is a known development
review, not fresh blinded qualification or independent consumer evidence.

Static inspection covered the verifier, its nested tests, the existing bounded
input reader, field scoring, canonical preview call order, and the coordinator's
Keras source disposition. The independent executable harness then ran 26 fresh
local-document fixture controls and one separately classified caller-precondition
counterexample. All assertions passed. No fixture command, Keras workload,
container, network request or provider/model call was executed.

## Observations

- Attachment parsing is capped at 128 KiB and 128 typed bindings. Individual
  source reads use the existing 2 MiB-plus-one bounded reader and reject
  nonregular/invalid-UTF-8 data. On Unix, pinned directory handles, `openat`,
  no-follow and nonblocking opens preserve the existing symlink/race boundary.
  The existing Windows concurrent-ancestor replacement limitation remains.
- Hashes bind full original UTF-8 bytes; CRLF changes fail rather than being
  normalized. Inclusive, one-based spans must exist. Repeated paths with different
  spans remain valid, while duplicate exact spans fail. Span validity does not
  establish that a span supports a semantic assertion.
- Exact candidate JSON, generation/assessment time and assessment source must
  match. Both command and context source paths must occur in the binding set.
  Fresh invalid attachments or changed source bytes produce a Failure check,
  `verification.passed=false` and an Unresolved candidate score.
- A successful integrity check retains at most Medium confidence. Spoofed `high`
  evidence metadata does not promote it. A manually self-consistent but
  semantically unestablished prerequisite demonstrates the deliberately limited
  mechanical responsibility; it remains Medium with completeness unresolved.
  Attachment absence retains the previous unassessed-candidate behavior.

`controls.json` retains every observation. The controls independently exercised
CRLF changes, invalid UTF-8, missing/directory/oversized sources, contained-path
violations, hash/range/duplicate/bounds failures, unbound command/context sources,
tuple/time changes, absent attachment and the positive distinctions above.
The author's separate nested tests cover additional cases including Unix leaf
and ancestor symlinks; this packet does not claim those author-run tests as its
own executions.

## Caller freshness limitation

The rootless `score_import_fields` API accepts a caller-supplied verification
report. Reusing an old Pass report after changing `sourceBindingsJson` can retain
Medium scoring. The independent counterexample records that behavior and the
fresh report's corresponding Failure/Unresolved result. This is an explicit
caller precondition, not a defect in the reviewed canonical flow: preview
verifies and immediately scores the same unmodified plan. No stale canonical
reuse was found in the inspected call sites.

The coordinator added concise API documentation requiring fresh verification for
the same unmodified plan/root, and reverification after changing sources. A
report observes integrity at verification time; it cannot prevent subsequent
filesystem changes. No report schema, public type or check-message parsing was
introduced to imply stronger authenticity or freshness.

## Retained execution and limits

`BEFORE.json` pins evaluated production files, fixture implementation, harness and
run helper before execution. The standalone harness generated a retained lock
offline, then executed with `--offline --locked` in a unique `/tmp` target. Its
source/lock files and command stdout/stderr/receipts are retained; generated
target/build caches and temporary fixture directories are excluded. The run took
12.060 seconds, exited zero, and confirmed unchanged evaluated source bindings
and fixture cleanup. The unused transport-patch Cargo warning is retained; the
core-only harness does not use the transport crate. Costs are null with explicit
exclusions, not zero.

The harness uses public APIs and local source documents; it never runs their
documented commands. The shared CLI was not rebuilt or invoked by this reviewer.
The coordinator/author own integrated CLI and broad workspace gates. The exact
Keras disposition freeze `2c53e516f15aafe6c80e16aa2b9ff1b104b2537d0a67857052e8f9737303545d`
continues to deny prerequisite completeness, high-confidence promotion and
consumer acceptance. Matching source attachments does not change that decision.

To reproduce the local controls, first obtain the shared Cargo slot and use a new
temporary target/output; the retained `run_controls.py` creates evidence paths
exclusively and cannot be rerun over this immutable packet. The exact Cargo
commands and environment boundary are recorded in `execution/` and the helper.
Reproduction is separate from any upstream execution authorization.
