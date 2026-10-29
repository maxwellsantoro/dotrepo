# Independent Go workflow-context review — 2026-10-29

Two YAML association defects were reproduced with the rebuilt first-party CLI.
The known IBM build/test and Redigo test controls pass, including actual escalation
at model budgets 0/2, but the following variants need correction before integration.
Redigo build remains outside this narrow guard and is not claimed repaired.

The final author implementation binding is
`b5952ccca9f35d5cb7298de4bb01870ff0098ab294ad080666e9799b4fd14a09`.
All 28 source/fixture bindings matched before testing and source snapshot capture.
The six Rust source files are retained under `source-before/`; original author/F1
packets and source/index records remain unchanged. Coordinator-owned expectation
additions are separate from the author's original expectation hash.

## Findings

1. **Quoted schema keys bypass the Redis prerequisite guard.**
   `go_context.rs:155-159` requires literal `jobs:` and lines 181-185 require literal
   `steps:`. Valid YAML `"jobs":` or `"steps":` makes the scanner skip the context
   altogether. The exact same Redis service plus `go test -race ./...` with plain
   keys leaves test unset; quoting either key restores scalar `go test ./...`.
   This loses the prerequisite and workflow flags through the original metadata
   fallthrough. Parse the supported scalar keys equivalently or retain an honest
   unresolved-context disposition for unsupported association; ignoring a known
   prerequisite context must not re-enable the default. This is not a request for
   a complete YAML interpreter.

2. **Literal environment data is treated as execution working directory.**
   `nonroot_directory` at `go_context.rs:45-57` scans any line with the text
   `working-directory:`. Its workflow/job-prefix callers at lines 189-190 do not
   restrict it to `defaults.run` or actual step properties. A valid multiline
   environment value containing `working-directory: examples` causes both root
   build/test defaults to be withheld, despite the actual job running unchanged
   `go test ./...` from root. Both workflow-level and job-level env variants were
   reproduced. Keep YAML scalar data separate from execution settings, and preserve
   the root-default control when no real cwd/prerequisite uncertainty exists.

[cli_controls.py](cli_controls.py) reproduces six synthetic workflow imports;
[cli-controls.json](cli-controls.json) retains all workflow bytes, exact CLI hash,
argv/results, generated manifests and evidence. The results are:

| Case | Build | Test |
| --- | --- | --- |
| Root control | `go build ./...` | `go test ./...` |
| Plain-key Redis service | `go build ./...` | unset |
| Quoted `jobs` Redis service | `go build ./...` | **incorrectly restored** `go test ./...` |
| Quoted `steps` Redis service | `go build ./...` | **incorrectly restored** `go test ./...` |
| Workflow env scalar mentioning working-directory | **incorrectly unset** | **incorrectly unset** |
| Job env scalar mentioning working-directory | **incorrectly unset** | **incorrectly unset** |

All commands ran only the local first-party importer on owned `/tmp` fixtures.
No upstream code, provider/model, network fetch or index write occurred. The first
review harness expected a native `.repo` path for an overlay output; it was corrected
to `record.toml`/`evidence.md` before the complete matrix. Two initial root-control
import invocations were diagnostic harness work, separate from the six reported
matrix runs. No output or timing here is consumer/fallback benefit evidence.

## Checks and limits

`cargo test -p dotrepo-core import::commands::go_context::tests -- --nocapture`
passed **12 tests**. The executed tests cover the six full importer fixtures,
native/overlay modes, explicit Manifest/ContribDoc/TaskScript alternatives,
unrelated ecosystem/job/example cases and actual `run_import_escalation` with
budgets 0/2 and a provider that rejects unexpected calls. Guarded unresolved fields
stay unset, candidate diagnostics remain and no provider call occurs in those
controls. CLI build passed; exact source and binary hashes are retained. Review
script Ruff/format and whitespace checks passed.

Typed in-memory blocked-field metadata and the shared adjudication-request gate
cover the ordinary deterministic/model/fallback ladder for contexts the scanner
actually recognizes. No notes, evidence prose, prior null values or protocol
fields became executable policy. The two findings concern source association
before that gate, not a demonstrated typed-metadata bypass. No frozen evidence,
source/fixture file, expectation, branch or record was edited by this reviewer.

This is bounded code/source review on known development cases, not held-out
qualification, execution validation or a general shell/YAML service audit. Wait
for the author's corrected stable-source handoff, then repeat these same cases and
positive controls before running combined gates. The original review remains
frozen; corrections and retests should be appended separately.
