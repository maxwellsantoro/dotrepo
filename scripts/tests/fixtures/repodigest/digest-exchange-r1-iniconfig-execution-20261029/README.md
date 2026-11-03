# Iniconfig bounded execution follow-up — 2026-10-29

**Accepted for this synthesized recipe in the pinned environment; not qualified
for the current public consumer.** The final amended trial completes two fresh
runs, each with exactly 54 passed test identities and no failures, errors or skips.
The separately authorized [independent reviewer](independent-review.md) confirms
the bounded result. This is one inspected development task, not a held-out sample,
independent adoption, production readiness or economic benefit.

This follows the [complete-source investigation](../digest-exchange-r1-iniconfig-closure-20261029/README.md).
That packet remains a source-only partial/no-go. This distinct execution phase
was authorized by the user's instruction to continue until a decision is needed.
No production policy, schema, public index or earlier result was changed.

## Accepted recipe and environment

Repository `github.com/pytest-dev/iniconfig`, revision
`a9e0ad14bcd0d9d3b68d2b699ce38399cbe64fdd`, root tree
`44da15d919d8e787f6357e07dbfb58643f7ac64a`; purpose `test`, repository scope,
component `null`, working directory `.` mapped to `/work/checkout`.

```sh
uv sync --locked --python /usr/local/bin/python3.12 --group dev
```

After disconnecting the setup network and checking the recorded isolation and
provenance conditions:

```sh
uv run --offline --no-sync --python /usr/local/bin/python3.12 pytest testing --color=no --junitxml=/work/results.xml
```

This is an attributed synthesis. The upstream CI command uses a sparse checkout
and a built wheel; that workflow and its artifact remain unexecuted. The commands
above depend on the complete Git checkout and tag context, not just 16 exported
source files. Git describes it as `v2.3.1-1-ga9e0ad1`; the editable distribution is
`2.3.2.dev1+ga9e0ad14b`.

The final image is
`digest-exchange-iniconfig-execution@sha256:c7fed9504414bf9f6bc6539b308b761e7711c64331f3359e9b8220186894d2e5`.
It contains CPython 3.12.16, uv 0.13.6, Git and iproute2. It runs on Docker Desktop
Linux arm64 with one CPU, 768 MiB memory and equal swap limit, 64 PIDs, nonroot user
1000:1000, read-only root, all capabilities dropped and no new privileges. There
are no host bind mounts, credentials or sockets. Executable `/work` is a 384 MiB
tmpfs; `/tmp` is a 64 MiB noexec tmpfs. Setup has a 180-second/64-MiB network budget;
tests have 60 seconds; each stage has a 1-MiB output cap. The replay budget is
600 seconds for two assigned runs, including its timeout control.

## Results and amendments

| Retained protocol | Assigned | Accepted | Observed result |
| --- | ---: | ---: | --- |
| [run-001](run-001/report.json) | 2 | 0 | Gzip transfer failed before candidate execution. |
| [run-002](run-002/report.json) | 2 | 0 | Setup succeeded; default noexec work mount prevented spawning pytest. |
| [run-003](run-003/report.json) | 2 | 0 | All 54 tests passed twice; network evidence predicate failed. |
| [run-004](run-004/report.json) | 2 | 2 | Fresh amended replay meets all bounded acceptance checks. |

There are eight assigned runs across four attributed protocols, six rejected and
two accepted. **2/2 applies only to the final amended protocol.** It is not an
unchanged-protocol success rate. The original specification and all earlier
reports remain intact. The [preparation](PREPARATION-AMENDMENT.json),
[transfer](TRANSFER-AMENDMENT.json), [executable-work-mount](WORK-EXEC-AMENDMENT.json)
and [final evidence](FINAL-EVIDENCE-AMENDMENT.json) amendments retain why the
instrumentation changed. Earlier code/input snapshots are under `preflight/`.
Preparation also retains failed container-creation/preflight attempts; they did
not execute candidate code. A first-party network diagnostic correctly rejects
Docker's attached `none` network under the empty-Networks predicate. Its container
was removed before the disconnected-bridge preflight succeeded.

The final replay takes 12.53 seconds overall. Every run retains stage logs,
resource counters, JUnit, before/after provenance, raw link/route captures and
Docker inspections. All 16 tracked hashes, commit/tree, clean tracked status,
interpreter binary/version, local editable import, package version and Git
describe value match the frozen expectations before and after testing.

[The static collection oracle](collection.py) parses literal dictionary keys and
parameter strings from the pinned source without importing it. It derives 18
tokenizer cases, four comment-line cases, one weird-line parameter case and 31
plain cases. Scoring compares the exact 54-case multiset, rejecting missing
parameters and duplicate substitutions. [The oracle receipt](collection-oracle.json)
binds those identities to the source hash.

Before the first upstream provenance import and again after tests, the final
runner requires empty Docker networks, no UP non-loopback links and no
non-loopback route across all IPv4/IPv6 routing tables. All four observations
satisfy this; test interface-byte deltas are zero. Kernel tunnel interfaces are
present but administratively down. `run-003` captured only their names and cannot
be retroactively accepted using the later observations. The timeout control
observes a live child, then proves terminal container state and removal; every
assigned container likewise has retained teardown proof.

## Current public policy and decision

[The diagnostic](policy-001/report.json) exports a temporary inferred record
through the actual Rust public exporter, then calls the unchanged reference
consumer. It abstains with `no-assessed-contextual-instruction`. A separately
labelled favorable-confidence synthetic diagnostic also abstains: the current
consumer requires extracted, high-confidence instructions and context. Neither
record is written to the public index. Observation cannot be relabelled as
extraction, and the current public context lacks revision/environment bindings.

[DECISION.md](DECISION.md) proposes the next reviewable choice. No further source
crawl or repeat of this same development task answers that product question.
F-05, a paid campaign, protocol changes and public rollout remain outside this
packet.

## Verification and limits

[Validation](validation.json) records 1,022 passing repository tests, including
29 focused evidence controls and real exporter/consumer controls, Ruff checks,
and the actual bounded Docker trial. Python tooling uses uv throughout.
[The cost ledger](cost-ledger.json) separates publisher, indexer and consumer
work. Git/image wire bytes, review tokens and complete maintenance cost are
unknown; local counters do not establish net savings.

The image and source are pinned, but isolated setuptools/setuptools-scm versions
and generated `_version.py` bytes are not retained. This is not a fully locked
build-dependency reproduction claim. Boundary observations are not continuous
tracing, and this first-party harness is not a general verifier against hostile
candidate code. It establishes these observed executions under the recorded
restrictions. Source, Git context, recipe, image/interpreter, environment, oracle,
instrumentation, policy or evidence-frontier changes require reassessment.

To inspect without upstream execution, read the frozen JSON/JUnit and run:

```sh
uv run pytest scripts/tests/test_iniconfig_execution_evidence.py
uv run python benchmarks/head-to-head/digest-exchange-r1-iniconfig-execution-20261029/policy_probe.py \
  --binary /absolute/path/to/dotrepo \
  --output /tmp/new-iniconfig-policy-result
```

The separate `runner.py` re-executes upstream setup/tests and requires the
matching locally prepared image plus deliberate execution authority. Its
`--output` must be fresh; it refuses to overwrite retained runs. `prepare.py`
describes initial preparation, while the final image/receipt and subsequent
changes are owned by the explicit amendments rather than silently regenerated.
