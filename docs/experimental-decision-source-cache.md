# Experimental retained source serving

The experimental Python decision-workflow service can expose verified source passages
and a tracked-file inventory alongside its repository facts and investigation
leads. Ordinary lookup and cached source hits need no model or network request.
This is an operator opt-in; the public Rust consumer and instruction
qualification policy are unchanged.

Admission validates the retained Git snapshot, then stores a content-addressed
inventory and the inspected UTF-8 source bodies. The admission receipt binds the
inventory digest; the inventory binds repository, exact revision, Git tree,
blob identity, mode and body digest. Uninspected paths remain explicit inventory
entries without retained bodies. Cached reads verify the root record, current
compiler policy, admission and inventory bindings, content digest and Git blob.
Admission receipts, inventories and bodies are append-only in SQLite.

Re-admit an existing trusted snapshot with the current compiler to populate the
cache. An older admission without a source inventory requires re-admission;
the reader does not invent one or silently fetch around a validation failure.
Source text remains untrusted publisher data. Retaining it does not establish a
complete instruction, current environment applicability, execution success or
permission to execute.

Build the first-party importer before admitting a snapshot:

```sh
cargo build --locked -p dotrepo-cli
```

Supply an operator-verified snapshot. For a new public GitHub source, the
existing bounded acquisition command can prepare one as a separate network
action (no model call or upstream code execution):

```sh
uv run python scripts/repodigest_acquire.py \
  --repository github.com/owner/project --revision <exact-40-hex-commit> \
  --output /path/to/new-acquisition
```

The resulting snapshot is at `/path/to/new-acquisition/owner__project`; review
its identity, coverage, errors and request ledger before ordinary admission.
This does not supply requirement assessments automatically. The compact test
fixtures in this checkout are historical regression data, not current project
recommendations or a bundled production catalog.

```sh
uv run --offline python scripts/repodigest_store.py ingest \
  --snapshot /path/to/verified-snapshot \
  --database /path/to/compiled.sqlite \
  --archive /path/to/new-admission

# Completely offline: facts plus source.list/source.read over retained evidence.
uv run --offline python scripts/repodigest_service.py \
  --database /path/to/compiled.sqlite --compiled-sources

# Source-cache control: the same source tools, without decision-workflow fact tools.
uv run --offline python scripts/repodigest_service.py \
  --database /path/to/compiled.sqlite --compiled-sources --source-only
```

To permit HTTP on genuine misses, also supply the existing `--source-catalog`
and `--traffic-log` options. The catalog independently constrains repository and
revision; where an admitted inventory exists, its tree and requested blob must
agree before HTTP. Integrity failures, changed compiler policy, invalid paths,
unsupported modes and catalog disagreement fail closed. Only a genuine missing
revision or uninspected body may reach the fallback. Neither source tool admits
new evidence or executes repository commands.

## Reuse source evidence from a consumer session

An operator can retain a useful HTTP fallback result for later consumers with
`scripts/repodigest_reuse.py`. Select the paths explicitly and supply trusted
SHA256 digests for the session's `events.jsonl` and `traffic.json`, for example
from an already reviewed immutable packet inventory. Computing a digest over
unknown input is not an independent trust decision. The importer checks the
retained full body against the pinned Git blob, a successful matching HTTP
receipt and a successful matching source-read result, including its numbered
passage. Failed reads, contradictory receipts, symlinks and unpinned paths refuse.

```sh
uv run --offline python scripts/repodigest_reuse.py \
  --previous /path/to/verified-snapshot \
  --session /path/to/retained-consumer-session \
  --output /path/to/new-candidate-snapshot \
  --path tests/check_types.py \
  --trusted-events-sha256 "$REUSE_EVENTS_SHA256" \
  --trusted-traffic-sha256 "$REUSE_TRAFFIC_SHA256"
```

This is a separate operator action. It performs no HTTP, model call, repository
execution or shared-store write. At most eight unique paths, 256 KiB per body,
1 MiB total selected source, 2 MiB events and 1 MiB traffic metadata are accepted;
the resulting snapshot remains limited to 96 inspected files. The candidate
snapshot must then pass the ordinary `repodigest_store.py ingest` admission.
Original fetch costs remain in the consumer receipt; importing those bytes is
not another publisher transfer. Repeated import of already retained files leaves
the snapshot unchanged and does not invent a new source-check time.

The `sourceReuse` metadata links original session hashes and event positions to
the body/Git identity, source revision and separate local import time. These are
operator-trusted historical receipts, not signed attestations or proof that the
whole file was read by a human. Normal refresh carries them only when both Git
blob and body digest stay unchanged. Changed/deleted bodies invalidate that
content witness; an unchanged body can retain its original source revision even
when the repository advances. Fresh source checks remain separate from the
historical receipt. This does not promote the agent's answer, proposed commands
or local environment assumptions into qualified procedures.

The inventory limit is 4 MiB, retained body limit 1 MiB, list page limit 100
paths and read limit 120 lines. All source JSON payloads are bounded to 32 KiB,
including HTTP and unavailable results; the transport envelope is additional.
Oversized passages fail visibly without silent line truncation. This bound also
applies to the existing direct HTTP source tool. Already fetched bytes still
count when the returned passage exceeds the limit.

Each reader memoizes at most four inventories and 8 MiB of serialized source
bodies. This is a logical byte bound, not a total process memory guarantee.
Optional trace retention writes exact source responses for independent review.
Its internal reads affect memoization hit counters: those counters are not
consumer-request hit rates. `logicalIndexBytesRead` and `logicalBlobBytesRead`
exclude record/admission SQL and filesystem/OS overhead and are not physical
I/O measurements. Per-call retrieval origin and returned/refused outcome are
reported separately from metered HTTP events.

The full comparison packet remains on the preserved experimental branch; the
[evidence inventory](research-evidence-20261030/README.md) retains its source
locator and verbatim conclusion. A replay of an old
request trajectory is counterfactual engineering evidence, not a new agent
productivity measurement. The fresh comparison separates direct HTTP, a shared
verified source cache, and decision-workflow facts over the same source cache. Acquisition,
refresh and maintenance costs remain part of the cost boundary; caching benefits
alone do not establish a benefit from semantic repository knowledge.
