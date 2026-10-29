# Collection driver amendment 1: three admission repairs

This append-only successor addresses the three findings in independent before
review `2329a7941142c543ea6450972f5b1041f78f02aad36d7b232b3059a0d773a7e1`.
The frozen 33-file parent and the before-review artifacts remain unchanged.
No daemon, Go, package, upstream/native task, Node or provider action ran for this
amendment. This is source/metadata plus entirely fake driver controls.

## Current driver acceptance and review subject

Authorization now requires an author freeze in the executing script directory.
Before comparing its identity, the driver checks that its plan hash and every
required script/local-file hash bind the current complete closure. The known
closure names are explicit; a missing declared file or mismatching artifact hash
cannot count as completeness. The current subject is:

```
{"driverPlanSha256": "<current plan bytes>",
 "authorFreezeSha256": "<current author FREEZE bytes>",
 "packetIdentity": "go01-collection-driver-amendment-1"}
```

The one-attempt authorization binds that author-freeze hash; the scoped acceptance
must carry this exact `driverSubject`. Its hash-bound `driverReviewFreeze` object
must explicitly declare state `independent-go01-collection-driver-review-passed`,
synthetic=false, scope `go01-collection-only`, the exact current `subject` and an
empty findings list. Execution authorization, native-task admission, campaign
admission and global-cache qualification in that review must all be false.
Arbitrary/unrelated JSON, the findings-bearing before review, stale plan/packet/
author-freeze subjects and findings-present/missing reviews are rejected before
daemon access. A hashed file alone is not a passed driver review.

The future passed review is external to the author plan hash, avoiding a circular
subject. It may be a review freeze or a separately hash-bound passed-subject report.
These remain internal coordinator continuity assertions, not cryptographic human
authority or a public protocol. No real passed review, scoped acceptance or live
authorization is created here. Synthetic tests construct isolated clearly disclosed
subject/review shape fixtures with fake transports; they do not substitute for the
independent after-review.

## Exact tmpfs and package metadata

The collection-specific inspect wrapper now requires exactly three tmpfs roots:
`/workspace`, `/workspace/dependency-cache` and `/tmp`. Options must be unique and
match the intended set: rw/exec/nosuid/nodev, size 8g/1g/512m respectively, uid/gid
1000 and mode 0700. Order may vary; duplicate/conflicting size/security/ownership
options, unknown options, missing roots and extra overlays are rejected.

The complete positive representation is bound to the retained actual npm setup's
before/final inspect bytes `6fcd10e5...`, plus the coordinator's retrospective
data-only check. These are historical fixtures, not fresh collection observations.
The exact safe create argv remains unchanged; no unsafe live container is asserted.
Historical helper files are imported unchanged; the stricter policy lives only in
this successor's wrapper.

For each Go package, `Dir` must equal the module directory plus the literal
ImportPath suffix. GoFiles/CgoFiles/TestGoFiles/XTestGoFiles must contain unique
literal `.go` basenames, with no path separators, traversal identities, colon or
control characters, and no duplicates across those fields. In the actual driver
path each selected file must also exist in the validated regular source inventory.
Legitimate Cgo/Test/XTest and zero-test-package records remain supported; unknown
or generated selected source is not silently established.

## Scope and validation

The three commands, source/image/Go-only projection, explicit prospective CC/CXX,
environment hash, resource/time bounds, raw output limits, before/after source and
tool observations, cleanup and null-cost rules remain the parent's. The source/
projection review `46211cce` remains bound. No npm, Hereby, helper build, task-body
command, network fallback, exclusion, resource increase or exported build artifact
is added. Listing can run init/TestMain if later authorized and remains distinct
from a completed task. All task/campaign/global-cache flags remain false.

The 59 prior fake driver/auth/archive/listing controls pass with current-subject
fixtures and selected-source membership. Forty amendment controls pass, including
the exact before regressions, historical/reordered tmpfs positives, malformed and
duplicate filenames, source-inventory membership, valid Cgo/XTest/zero-test cases,
stale acceptance/review identities, findings-bearing/unrelated reviews and missing
author-freeze bindings. Two copied fake client cancellation/deadline controls pass.
No real process/socket is allowed by these controls.

The owned Node observer algorithm/control scripts and used Python helpers are
unchanged; `observer-control-reuse.json` binds the parent's six authorized controls
and verifies source-function equality plus the same local tool bytes. Node was
not rerun here. Metadata verification and Ruff check/format pass. The generated
development controls are retained separately. Full source/cache archives were not
rescanned; source/projection review remains its own evidence boundary.

Independent amendment review and root's separate scoped acceptance/one-attempt
authorization remain required. Review copies must omit generated controls JSON
before replay (exclusive writes). Controls create a temporary synthetic author
freeze; the real packet freeze remains immutable. No old frozen artifact, shared
source, record, branch, publication or installed default changed.
