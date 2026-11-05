# Durable local decision workflow

`scripts/decision_workflow.py` is the versioned `dotrepo-decision-source/1`
entrypoint for the experimental Python decision workflow. A workspace retains
shortlists, search budgets, unfinished attempts, tool results and completed
decisions across process exits. It uses the existing admitted SQLite source
store, source reader and requirement assessments. This is a source-install
candidate, separate from the published Rust CLI/MCP packages.

The command does not infer requirements or select a best repository. A supported
decision establishes preliminary support for the caller's mapped requirements;
missing or conflicting evidence remains unknown. It never executes selected
repositories, fetches missing sources or grants execution permission.

## Set up a fresh source environment

Use a checkout containing this command, Python 3.12 or newer, `uv`, and the Rust
toolchain declared by the checkout. From the repository root:

```sh
uv sync --dev --locked
cargo build --locked -p dotrepo-cli
uv run --offline python scripts/decision_workflow.py --version
uv run --offline python scripts/decision_workflow.py --help
```

The native importer is needed to admit source snapshots, not to inspect an
already retained decision. The [source-store guide](experimental-decision-source-cache.md)
owns snapshot identity, bounded acquisition and admission. Start with an
operator-verified snapshot and admit it into a new database:

```sh
uv run --offline python scripts/repodigest_store.py ingest \
  --snapshot /path/to/verified-snapshot \
  --database /path/to/decision-store.sqlite \
  --archive /path/to/new-source-admission
```

This does not invent capability assessments. When a trusted operator has an
assessment and review, admit them through the separate
[assessment workflow](experimental-decision-requirements.md#admission-and-invalidation):

```sh
uv run --offline python scripts/repodigest_requirements.py \
  --database /path/to/decision-store.sqlite \
  --assessment /path/to/assessment.json --review /path/to/review.json
```

The reviewer, semantic alignment and source freshness remain operator
responsibilities. Without aligned assessments, decisions correctly remain
unknown/none-established. Historical regression fixtures and synthetic test
assessments are developer controls, not a production catalog or recommendations.

Finish all admissions before creating a workspace. Use an ordinary SQLite
rollback-journal database with no active writer, `-wal` or `-journal` sidecar:

```sh
uv run --offline python scripts/decision_workflow.py init \
  --workspace ./research/decision-visit-1 \
  --database /path/to/decision-store.sqlite
```

The workspace directory must be new. Initialization pins the database's absolute
path and exact SHA-256, plus the source-store and assessment-reader policies.
There is no implicit source-store rebinding. A separately admitted update or
policy change requires a new workspace; retain the previous workspace to compare
historical decisions. Do not admit records concurrently with consumer calls.

## Discover, inspect and decide

Each `call` reads a small UTF-8 JSON object from `--request` and returns a JSON
envelope. The actual tool response is under `result`; `sequence`, `recordedAt`
and `policies` identify the saved call. The short tool names preserve the argument
shapes documented by [bounded selection](experimental-decision-selection.md):

| Tool | Request and purpose |
| --- | --- |
| `find` | `{"query":"markdown"}` discovers leads within the admitted profiles. |
| `shortlist` | `{"queries":["markdown"]}` creates a selection. Add `selectionId` to refine the same selection. |
| `describe` | `{"repository":"github.com/owner/project","revision":"<40 lowercase hex characters>"}` inspects a lead and its assessment keys. |
| `qualify` | Exact `candidates` and mapped `requirements` check source support before deciding. |
| `source.list` / `source.read` | Exact repository/revision, plus path/range for reads, inspect retained original sources. Missing bodies never trigger HTTP. |
| `decide` | `selectionId`, exact `candidates`, mapped `requirements` and optional `unmappedRequirements` finalize the decision. |
| `selection_status` | `{}` lists accounting; `{"selectionId":"selection-1"}` reads one retained selection. |

For example, save `{"queries":["markdown"]}` in `./shortlist.json`, then run:

```sh
uv run --offline python scripts/decision_workflow.py call \
  --workspace ./research/decision-visit-1 --tool shortlist \
  --request ./shortlist.json
```

Use the returned selection ID and exact revision/component. Read `describe`,
align every mandatory requirement with its returned key and limitations, then
submit the `qualify` request. A final request has this shape; replace the target
and key with evidence actually present in the admitted store:

```json
{
  "selectionId": "selection-1",
  "candidates": [{
    "repository": "github.com/owner/project",
    "revision": "0000000000000000000000000000000000000000",
    "component": "."
  }],
  "requirements": [{"key": "task.explicit-claim-key", "expected": true}],
  "unmappedRequirements": ["Any mandatory condition without aligned evidence"]
}
```

An unresolved mandatory condition prevents a supported selection. An empty
candidate list can close an unsuccessful search without claiming global
absence. Run the final request with `--tool decide`. Every command can run in a
different process: follow-up queries retain the three-search budget and completed
selections refuse further changes.

## Return to retained work

Exit the process, then inspect the workspace without the source database:

```sh
uv run --offline python scripts/decision_workflow.py inspect \
  --workspace ./research/decision-visit-1 --selection selection-1
```

Inspection returns retained selections and the complete call ledger, including
failures. Each completed decision retains the original qualification response:
source references/hashes, assessed revision, source status and limitations. Its
call's `assessmentBindings` retain each verified assessment capsule's original
`sourceCheckedAt`, target and policy/hash bindings. `recordedAt` is the local
tool-call time, not a renewed
source inspection date. Inspection makes no current-source or live freshness
claim. Calls at a later visit must still satisfy the existing source-age policy;
matching database bytes do not make an old source observation fresh.

The workspace owns `workflow.sqlite3`; the admitted source database stays
separate and read-only. Back up the entire workspace when idle and keep the
source database or its independently verified backup if future source reads
are needed. Inspection includes saved passages from earlier source-read calls,
not every source body from the database.

## Recovery, bounds and accounting

Exit status **0** means a tool returned a result (which can contain unknown or
unavailable evidence), **2** means an attempted tool call failed and was saved,
and **1** means configuration/workspace refusal before a call could be committed.
Retain the JSON response for every attempt.

- If the admitted database disappears, inspection still works. Tool calls save
  an explicit failure and create no replacement database. Restore its exact
  original bytes at the bound path, then retry. Changed database bytes or reader
  policies require a new workspace; original results remain historical.
- A missing exact source revision/body is unavailable evidence; an untracked
  path is refused. Check `source.list` and the saved admission before selecting
  another exact source. New acquisition/admission is an explicit operator step,
  followed by a new workspace, never a silent fallback or freshness renewal.
- A corrupt state digest or unsupported workspace format refuses operation;
  it never resets the ledger. Preserve the damaged files and restore a verified
  idle backup into a separate directory. Initialization refuses an existing
  directory and cannot overwrite saved decisions.
- SQLite serializes workspace calls with an immediate transaction and a
  five-second lock timeout. A committed tool result and its session state are
  atomic. A crash before commit rolls back both; that interrupted local work is
  not represented as a completed ledger event. Check `inspect` before retrying
  after uncertain output. If a decision already committed, inspect it rather
  than trying to replace it. Keep external process logs for crash accounting.

Each workspace permits 16 selections, 256 committed calls, 2 MiB of serialized
selection state and 16 MiB of serialized call events. Each request/result is at
most 64 KiB; existing tools retain their tighter response and query bounds. A
full workspace refuses new work and retains prior results. Archive it explicitly
and initialize another workspace; it is not an unbounded history service.

The immutable-store check reads the entire database before and after successful
tool calls. `storeIntegrityBytesRead` counts those logical file bytes (once at
initialization, up to twice per call), separately from source-cache counters.
This conservative check has a real cost; it does not establish a consumer
efficiency benefit. Failed source calls retain their cache accounting too.
Physical disk I/O, CPU, human time and billing are not inferred from these
counters. The frozen-store and workspace digests detect ordinary accidental
changes; they are not authenticity proofs or a filesystem sandbox against an
active same-user writer.

Fresh-process tests cover the complete decision path, restart, immutable
completion, unknowns, search exhaustion, source/database loss and recovery,
policy/database substitutions, corrupt state and bounds. They are implementation
evidence. Useful repeated decisions and equal-cache economic comparisons remain
the separate D2 outcome gate in the [roadmap](../ROADMAP.md#active-execution-order).
