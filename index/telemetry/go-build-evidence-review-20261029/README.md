# Independent review of Go build evidence eligibility

The final narrow patch passes this review's eligibility and adjudication controls.
It withholds a build inferred solely from root `go.mod`, retains that attributed
candidate as an unresolved diagnostic, and excludes it from bounded adjudication
requests. The existing Go test default remains unchanged. Explicit maintainer
sources remain eligible, including conflicts that require adjudication. A workflow
tagged build survives as that exact observed variant; this review does not turn
it into proof of a repository default or applicable instruction.

This reviewer authored the prior Go scope/setup guard and worked on the known F1
development cases. The current review is separate from the build-rule author and
focuses on the new eligibility boundary; it is not a fresh blind or held-out
evaluation. No source/index mutation, upstream execution, model/provider call,
network request, or container execution occurred during this review.

One blocking defect was reproduced before correction: when `README.md` and
`CONTRIBUTING.md` declared conflicting eligible builds, removing the conventional
module build set the whole-field blocked bit and suppressed both declarations.
The immutable `before-conflict/` packet binds the actual first-party CLI build,
source snapshots, conflicting inputs and observed erroneous module-only note.
Its freeze SHA256 is
`d160760b719b427b9b78af6c6563f83b4c11bf367fa5807c9ae4bb31495f0cc7`.
The CLI does not expose requests; request suppression was source-path proof.

The author corrected this with a separate metadata-only withheld flag after the
existing scope/setup filtering. It only blocks the field when no independently
eligible filtered build exists. Original context-refusal bits remain enforced.
The final direct core regression observes both explicit conflict alternatives in
the request and no `go.mod` alternative; the scoped conflict still produces no
request. These observations close the original finding without relaxing the
earlier context block.

`after-conflict/focused-tests.log` retains the independent run of all 20 Go guard
tests, including real importer/adjudication controls at budgets 0 and 2, raw
diagnostic retention, module-only/refused workflow cases, explicit sources and
the conflict regression. `after-conflict/observations.json` retains five actual
first-party CLI imports against one integrated binary: module-only, explicit,
explicit-conflict, exact tagged workflow, and service-dependent test refusal.
The conflict remains unresolved but no longer gets the erroneous module-only
field-block note. The raw request contract is proven by core tests rather than
the CLI output.

The reviewed Go files match the author's final source bindings. The shared
`fields.rs` and `import/mod.rs` also include the subsequently coordinator-owned E1
mechanical verifier wiring. `after-conflict/source-bindings.json` and snapshots
bind that integrated state and binary, without rewriting the earlier author's
focused evidence. The integrated importer quality tests also passed separately
in the E1 packet. Ruff check/format passed for the independent CLI control.

No remaining blocking finding was identified in this bounded scope. The broader
Go default/evidence policy and YAML applicability are outside this review; the
prior scope/setup guard is retained rather than requalified here. This is a
regression/eligibility result, not source completeness, upstream build success,
consumer benefit, or an independent product trial.
