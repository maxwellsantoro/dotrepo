# Retain and hand off one user source interpretation

`scripts/decision_findings.py` is a maintained experimental source command for
retaining one useful user-authored interpretation with exact admitted source
bindings. It addresses the case where a consumer reaches a useful scoped
conclusion that strict requirement qualification does not express. It writes a
separate immutable file store. It does not create requirement assessments, change
`qualify`/`decide`, fetch sources, invoke a model, or run repository code.

This is a bounded local adapter for `lazycollective.finding-handoff/1`, not a
published cross-product protocol. Its sources are normalized GitHub repository
identities, exact Git revisions and admitted UTF-8 Git blobs. Page sources and
other representations need their owning adapter and remain outside this command.
Passing synthetic controls establishes mechanics; useful second-reader transfer
and comparison with the same cached sources require separate outcome evidence.

## Commands and storage

Use an already admitted frozen source database. The existing
[source cache guide](experimental-decision-source-cache.md) owns acquisition,
admission, source policy and source limits. All commands below run offline:

```sh
uv run --offline python scripts/decision_findings.py record \
  --store /path/to/sender-findings --database /path/to/compiled.sqlite \
  --finding /path/to/finding-input.json --evidence-root /path/to/retained-evidence

uv run --offline python scripts/decision_findings.py inspect \
  --store /path/to/sender-findings --sha256 <finding-sha256>

uv run --offline python scripts/decision_findings.py recall \
  --store /path/to/sender-findings --sha256 <finding-sha256> \
  --database /path/to/current-compiled.sqlite --policy /path/to/recipient-policy.json

uv run --offline python scripts/decision_findings.py export \
  --store /path/to/sender-findings --sha256 <finding-sha256> \
  --output /path/to/new-envelope.json

uv run --offline python scripts/decision_findings.py receive \
  --store /path/to/isolated-recipient-findings --database /path/to/own-compiled.sqlite \
  --envelope /path/to/new-envelope.json --policy /path/to/recipient-policy.json
```

`record` verifies full source bodies through the existing admission-bound reader
and verifies the explicitly selected local evidence. `inspect` works after
restart even if the source database is unavailable; it displays a retained
historical finding, not a new validation. `export` preserves the original finding
and source dates and adds `exportedAt`. Its output must be a new file.

`recall` is the read-only returning-reader path. Supply a known finding digest
and the same explicit [recipient policy](#recipient-policy-and-explicit-interpretation-review)
used by `receive`. It verifies the stored finding and its dependencies against
the reader's current admitted database, applying the existing source-age,
representation, full-body integrity and changed/missing-source rules. It emits
one compact `dotrepo-finding-recall/1` JSON object: the original claim, task scope,
assumptions, limitations, attribution and dates; original source bindings joined
with their current checks; aggregate `sourceStatus`; policy and verification
accounting. It does not export an envelope, write a receipt, fetch sources or
include unrelated findings, call history or source bodies. Save stdout when a
retained check receipt is needed.

The separate `checkedAt` records this check; `findingCreatedAt` and every
`originalObservedAt` remain unchanged. `interpretation.disposition` is always
`unreviewed`, with scope/time/attribution issues visible even when sources are
current. A caller must still choose a relevant finding and judge whether its
meaning and assumptions answer the task. `recall` does not search natural-language
questions, resolve conflicting interpretations or create semantic assessments.
Use `inspect` for the stored original and `source.read` for original passages.
The compact result is limited to 64 KiB; an oversized result refuses without
truncating the claim or altering storage. This interface reduces required
bookkeeping steps; actual agent-token savings require the matched evaluation.

Store filenames derive only from locally computed full SHA256 digests:
`finding-<digest>.json`, `envelope-<digest>.json`, `receipt-<digest>.json`. No sender
ID, repository path, evidence locator or attribution selects a destination.
Commands never replace stored bytes, and different conclusions and review
receipts remain separate. Existing bytes are verified before idempotent reuse;
corruption refuses instead of resetting the store. A store admits at most 256
regular files, each at most 64 KiB. Preserve a full store and select another one.
These are application-level immutable writes and integrity checks, not protection
against an operator editing files or a concurrent hostile filesystem writer.
Use one writer and a dedicated store directory.

`record` returns the finding digest/path and verification receipt digest. Receipts
retain database integrity bytes read, source-cache logical bytes read and local
evidence/input bytes read. These are logical accounting boundaries, not physical
disk I/O, CPU, token or monetary measurements. Source admission, preparation,
failed commands and recipient interpretation work must also be counted in an
outcome comparison. Refused CLI calls return a structured error and exit 1;
retain that output externally when recording unsuccessful attempts.

## Finding input

The input is a UTF-8 JSON object with exactly these fields. Empty claim, scope,
IDs and origin are refused. There are 1–16 unique source identities, a claim of
at most 32 KiB, and at most 64 KiB for the entire input/export. Duplicate JSON
keys, nonfinite numbers, unsafe source paths, unsupported versions and symlinked
local inputs, database paths, evidence paths or output parents refuse.

```json
{
  "id": "original-user-finding-1",
  "origin": "my-consumer-session",
  "claim": {"text": "A bounded user interpretation; execution remains unknown."},
  "taskScope": "The exact task question and component boundary.",
  "limitations": ["Source declaration only; no execution observation."],
  "assumptions": ["Declared constraints apply to this captured component."],
  "attribution": {"author": "original consumer", "product": "source consumer", "recordId": "answer-1"},
  "findingCreatedAt": "2026-10-30T12:10:00Z",
  "originEvidence": {"locator": "answer.json", "sha256": "<64 lowercase hex>"},
  "sources": [{
    "kind": "repository",
    "repository": "github.com/owner/repository",
    "revision": "<40 lowercase hex>",
    "path": "component/go.mod",
    "sha256": "<64 lowercase hex over the entire body>",
    "representation": "git-blob:utf-8",
    "lineRange": [1, 3],
    "originalObservedAt": "2026-10-30T12:00:00Z",
    "originalTimeReason": null,
    "originalObservationEvidence": {"locator": "original-source-read.json", "sha256": "<64 lowercase hex>"}
  }]
}
```

The digest placeholders above must be replaced by actual digests. Source
`repository` is the exact normalized admitted identity, not a display label.
A synthetic local admission must retain its synthetic identity/revision; keep
the original repository label and the lack of upstream admission in limitations
or assumptions. A line range is optional (`null`) and never changes the full-body
digest boundary. Assumptions and limitations are lists of at most 32 bounded
strings. Their absence of entries does not prove that no other premises exist.

The three attribution fields and `findingCreatedAt` can be `null` when unknown.
A source with no original observation time must use `originalObservedAt: null`,
a nonempty `originalTimeReason`, and `originalObservationEvidence: null`. Do not
copy a newer cache validation time into these historical fields.

For a known original source time, `record` requires a retained completed
`source.read` call receipt. Its result must bind the exact repository, revision,
path, full SHA256 and `sourceCheckedAt`; its `recordedAt` must lie between that
source observation and the original finding creation. A bare undated result or
a later reread does not establish the original finding's source observation.
The command preserves literal UTC RFC3339 timestamps. It does not invent a
missing finding date or backfill a missing source date.

`--evidence-root` is an explicit caller-selected local evidence boundary.
Relative locators are resolved under that root; absolute locators must be within
it. Origin evidence is limited to 2 MiB and source-call evidence to 64 KiB.
Their hashes must match. These hashes and names describe local provenance; they
are not authentication, independent acceptance or proof that the interpretation
is correct. Receivers never open these sender locators, including local-looking
paths and URLs.

## Recipient policy and explicit interpretation review

A policy is an explicit local JSON file:

```json
{
  "id": "my-recipient-policy-1",
  "taskScope": "The exact task question and component boundary.",
  "maxSourceAgeSeconds": 86400
}
```

The maximum age must be finite and between zero and one year in seconds. The
recipient validates its own current admitted repository revision, full body,
representation, admission/compiler policy and original admitted check time.
An old retained revision alone does not establish current evidence. There is no
network fallback or database write. A verified different current full-body hash
is `changed`. When the original bound body is still verified locally, a different
current admitted Git blob also proves a byte change, even if the current body is
uncached; the receipt preserves that change and the unavailable-body reason.
Repository revision changes alone do not prove that a cited source changed:
verified identical bytes can remain `current` across revisions. Missing paths,
unsupported modes, corrupt/unavailable bodies, unverified representation or stale
sources remain `unknown` when no byte difference is proved. Same-blob current
bodies that were not inspected remain conservatively `unknown` under the reader
policy. Exact policy-compliant source is `current`. Aggregate precedence is
`changed`, then `unknown`, then `current`, with every individual reason retained.
This is the recipient's admitted-store boundary, not live upstream freshness.

The receive receipt separately records the envelope digest, recipient policy and
its digest, checking time, per-source results, `sourceStatus` and `interpretation`.
The default disposition is `unreviewed` even for current source bytes. Broader
recipient scope, unknown original dates and incomplete attribution remain
explicit interpretation issues. They do not alter an independently current
source status.

After inspecting meaning, scope and limitations, an explicit recipient can make a
separate review file and pass it with `receive --review /path/to/review.json`:

```json
{
  "envelopeSha256": "<full digest returned by export>",
  "taskScope": "The exact recipient policy task scope.",
  "reviewer": "explicit recipient reviewer",
  "disposition": "accepted",
  "reason": "The reason for this scoped interpretation judgment."
}
```

Allowed explicit dispositions are `accepted`, `rejected` and `conflicting`.
Acceptance requires a fresh source check in this receive operation, `current`
source status, exact scope alignment and complete original time/attribution
metadata. It is a recipient interpretation receipt, not reviewed tool assessment
admission or execution authority. Claimed names and retained evidence hashes
still do not authenticate a sender. Conflicting and rejected interpretations
can be retained even if source status is current, changed or unknown. Every
review produces a separate immutable receipt and leaves the original envelope
and prior dispositions available.

Focused developer controls live in
`scripts/tests/test_decision_findings.py`; run them with
`uv run --offline pytest -q scripts/tests/test_decision_findings.py` after the
existing native importer has been built. The coordinator owns combined gates and
independent acceptance. Product packaging, public protocol stabilization and
useful-transfer outcomes have separate boundaries.
