# Go-01 oracle preparation — source only

This packet prepares a task-specific post-run Go JSON oracle for the unchanged
Microsoft TypeScript repository-default `go-01` task at
`25f823dc198a00744b458a7bc6984359f0dd7cac`. It authorizes no cache preparation,
Docker call, collection, upstream execution, package/source fetch, model call or
VM change. The old incomplete attempts and original all-skips-reject oracle are
unchanged. No native identities, package counts, outcome or retry cost were
observed here.

The original full command remains:

```text
GOTESTSUM_JSONFILE=/workspace/go-test-events.jsonl GOFLAGS="-p=1 -count=1" npx hereby test
```

It runs from the repository root. The source-owned wrapper reaches the complete
`test:tsc` Go `./...` suite, not `test:all`; no package/test filter or extra
generation command is introduced. The preceding frozen proposal owns the common
image, proposed TMPDIR change, resource conditions and incomplete setup/cache
questions. `source-bindings.json` binds that proposal and the exact existing full
archive. Its 280,422,400 bytes were rehashed locally; source lines below were
read as data, without running Go or the wrapper.

## Exact exclusion proposal

`policy-proposal.json` remains **unaccepted**. Its unresolved environment digest
and missing acceptance also prevent native use. It proposes 380 exact identities:

| Source condition | Proposed exact identities | Why this can describe the default outcome |
| --- | ---: | --- |
| Immediate unconditional `Known failing fourslash test` skips | 377 top-level cases | Maintainer-authored disablement precedes each body; source hash and exact function/line are retained |
| Immediate unconditional bare fourslash skip | `TestAutoImportPackageRootPathTypeModule` | Separate case with no skip message; requires its exact native terminal skip diagnostic |
| Empty default replay flag | `internal/lsp.TestReplay` | The source flag defaults to empty and the unchanged wrapper supplies no replay argument; the test is an optional replay facility |
| Immediate unconditional ATA Todo skip | `internal/project/ata.TestATA/deduplicate_from_local_@types_packages` | The literal subtest begins with a Todo skip before its body; the proposed native spelling must be confirmed with the frozen tool's naming rules before acceptance |

These are declarations of excluded behavior, never passed/exercised behavior.
The ATA exclusion covers only that exact nested identity; its parent and other
children remain subject to normal coverage checks. Replay acceptance depends on
the default argument/environment contract staying unchanged.

Each entry binds the original path, source SHA-256, line span, excerpt, reason
and condition. The oracle pins the canonical exclusion-set hash and permits only
byte-equivalent entries from this proposal. An accepted successor policy may
select applicable entries, but cannot add a capability assumption, prefix/suffix
rule or newly observed failure to this oracle's allowlist. A broader policy needs
a separately reviewed source-grounded amendment before execution.

## Remaining source conditions

`skip-source-ledger.json` binds all 469 direct skip sites from the proposal's
lexical `_test.go` inventory, plus **11 additional direct skip sites in five
non-test helpers** found in the existing archive. This is a lexical diagnostic,
not an exhaustive Go control-flow analysis or evidence that every site is active.
After the 380 exact proposals, 89 lexical test-file sites and all 11 helper sites
remain unapproved. Build-tag, platform, benchmark and forwarding helpers can
describe different or inactive situations.

`unresolved-conditions.json` retains an important additional boundary: compiler
emit verification declares eight source-named fixture exclusions, while compiler
option helpers declare seven unsupported-option predicates. Their exact full
dynamic suite/configuration identities have not been derived. Fuzz seed
predicates also need exact identities and input-condition evidence. None receive
a pattern-based exception here.

Fanotify availability, NameToHandleAt, watcher capabilities, filesystem behavior
and permissions require source-bound conditions and separate probes before any
proposed exclusions. Nonroot/cap-drop does not prove every condition. Missing
embedded bundles, Node, fixtures or home state may indicate lost prerequisites;
they are not automatically acceptable exclusions. Any unexpected skip at any
nesting depth therefore remains unresolved under the present oracle.

## Oracle and collection contract

`oracle.py` scores retained evidence after agent/operator decisions. It launches
no processes and must never gate an agent's command choices against hidden gold.
It requires:

- A separately completed and frozen native collection manifest with the full
  package set, including zero-test packages, and exact top-level test/example/
  fuzz identities. `collection-required.json` is deliberately empty and rejects.
  The static 6,028 lexical identifiers are not native expectations.
- Equal exact revision/archive/image/environment/command/scope bindings across
  collection, accepted policy and execution; SHA bindings for collection raw
  output, package inventory, collection receipt, policy and execution events.
  Collection and policy timestamps must precede execution.
- Full raw Go JSON, package start/terminal states, run and terminal evidence for
  every intended top-level identity and every observed nested identity. Wrong
  packages, listing-only streams, missing terminals, duplicate runs, malformed or
  truncated data and unknown all-depth skips fail closed. Declared skips also
  require their witnessed message or exact bare-skip terminal diagnostic.
- Complete setup/wrapper/event controls, intact tracked source, no timeout,
  resource failure or transport error, and a consistent native exit. An entirely
  excluded test set cannot stand in for active coverage.
- Complete terminal assertion failures may be an observed default-command
  outcome with `testsPassed=false`: all active coverage must still terminate,
  failed tests must have exact native failure diagnostics, packages must agree,
  and exit must be one. Build/runtime/resource failures remain unresolved.

The oracle checks internal receipt consistency. It does not authenticate claimed
provenance, prove that a manifest is the full native collection, or independently
establish external acceptance. A future driver/reviewer must bind actual raw
collection receipts, complete package discovery, exact environment/tags, command
and policy acceptance to those assertions before native use. Source-controlled
output can also resemble diagnostics; inconclusive classification remains for
independent adjudication rather than a claimed general Go failure classifier.

Synthetic controls explicitly label themselves synthetic; even their positive
cases always return `taskOutcomeObserved=false`. The candidate-completion flag
exists only to test scoring logic. No fixture count is a proposed native count.

To rerun synthetic controls into a fresh output:

```sh
uv run --offline --no-sync python benchmarks/head-to-head/f05-go01-oracle-preparation-20261029/controls.py --output /tmp/dotrepo-go01-oracle-controls-unique.json
uv run --offline --no-sync python benchmarks/head-to-head/f05-go01-oracle-preparation-20261029/verify.py --archive --output /tmp/dotrepo-go01-oracle-source-check-unique.json
uv run ruff check --no-cache benchmarks/head-to-head/f05-go01-oracle-preparation-20261029
uv run ruff format --check --no-cache benchmarks/head-to-head/f05-go01-oracle-preparation-20261029
```

`controls-final2.json` is the final control run; preceding successful control
snapshots are retained. Its 60 controls cover exact top-level/nested/default replay/bare
exclusions, assertion failure, excluded-only and listed-only stand-ins, unknown
deep skips, prefix collisions, late freezes, changed bindings, malformed JSON,
missing package/test evidence, source/control/resource failures and numeric/bool
aliases. None call Docker, Go, npm or a provider.

The future CLI is:

```sh
uv run --offline --no-sync python benchmarks/head-to-head/f05-go01-oracle-preparation-20261029/oracle.py --events EVENTS.jsonl --collection COLLECTION.json --policy ACCEPTED_POLICY.json --execution EXECUTION_RECEIPT.json --output NEW_RESULT.json
```

This describes post-run scoring; it does not authorize producing those inputs.
`--synthetic` is required for synthetic inputs. Output creation is exclusive.

## Exact remaining gates

1. Independently challenge the exact exclusions, dynamic helper/fixture/config
   identities, seed predicates and conditional setup/platform dispositions.
   Resolve source facts and freeze any amendment before tests; preserve the
   original proposal and old failures.
2. Obtain explicit coordinator acceptance of scope, exclusion policy,
   environment, numeric collection/execution budgets and output/cleanup bounds.
   Current proposal flags remain false.
3. Separately authorize one bounded download-only preparation, audit actual
   cache content/provenance, and settle normal offline npm lifecycle behavior
   versus ignored-hook equivalence. No fourth cache exists from this packet.
4. Separately authorize successful native package/test collection under the
   exact accepted source/platform/tags/environment. Freeze its actual full set,
   raw outputs and receipt before tests. Retain collection failure as incomplete;
   never substitute lexical counts or execution-observed identities afterward.
5. Independently review the frozen join, then separately authorize any actual
   unchanged full-wrapper attempt. Preserve all outcomes, costs and limitations.

This is a known development/operator diagnostic, not fresh blind gold, a fourth
qualified environment, the 72-session campaign or consumer-benefit evidence.
