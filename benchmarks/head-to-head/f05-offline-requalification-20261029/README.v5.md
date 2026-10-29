# Offline driver amendments: retained failures and exact default phases

This append-only successor preserves v1–v4, their plans, traces and freezes.
Current plan is `plan.v5.json`, SHA-256
`2d44b468d8954b42210cce44ae12c2571a835b8a89154d585a20f4cdbbce90e6`;
current executable is `driver.v5.py`. **No Docker, upstream project workload,
package download, provider/model call or index/profile access occurred.** Root
has approved the bounded Rust outcome policy below, not live execution or cache
admission. Independent review and explicit run acceptance remain gates.

Independent v3 review exposed two material defects. Accepted source/cache
preflight failure could occur before output and finally handling, losing the
attempt receipt. The Rust scorer could accept two passing unit tests followed by
a rustdoc compilation failure as a complete task outcome. V4 corrected these.
Further independent v4 review found that legacy suffix matching could accept an
unrelated test name ending with an expected name. V5 corrects exact case identity.
`freeze.v4.json` and `independent-exact-case-counterexample-v4.json` retain the
intermediate evidence; no old result was rewritten to pass the new checks.

The driver now creates an exclusive accepted-attempt directory, acceptance
binding and `attempt.json` **before** source/cache preflight. Hash, inventory or
size failures preserve their stage, full error, expected input identities,
preflight/work/total elapsed time, outcome nulls and unknown cost in `result.json`.
If container creation was never attempted, cleanup is explicitly unattempted and
no daemon call occurs. Failed or missing authorization still refuses before any
daemon activity. A partial create triggers bounded cleanup and records cleanup
failure separately from native outcome.

CLI metadata verification is separately measured outside the 1,800-second task
deadline and included in total measured operator effort. Direct API callers that
do not supply that timing receive an explicit unknown value. Accepted input
preflight, provisioning, offline setup, discovery, tests and checks share the task
deadline; cleanup retains its separate 60-second grace. No unknown measurement is
converted to zero cost.

Rust scoring now consumes stdout, stderr, process exit and transport/timeout
error, with explicit stage coverage:

- Normal success requires both exact full unit IDs, consistent terminal case
  states and two-test summary, the separate zero-case doc summary and doc marker,
  no compile/setup/unknown failure diagnostic, and exit 0.
- Complete unit assertion failure can supply the requested default-command
  outcome under the coordinator-approved frozen policy: both exact unit cases
  terminal, at least one `FAILED`, consistent summary, native exit 101, no
  transport error, ordinary Cargo `--lib` test-failure diagnostic and no
  compiler/setup diagnostic. The doc phase must be absent and is recorded as
  **unexecuted-default-stop**. `phaseCoverageComplete=false`; no doc execution or
  comprehensive behavior coverage is claimed.
- Unit success followed by doc compilation/setup failure, missing phase summary,
  contradictory status, timeout, unknown diagnostic, wrong case prefix/module,
  duplicate ID or a bare suffix match is noncompletion. Nonzero exit alone cannot
  establish either a completed assertion failure or an incomplete setup.

Exact unit IDs are `link_type::tests::test_link_type_from_pcap_supported` and
`link_type::tests::test_link_type_from_pcap_unsupported`, derived from the unchanged
historical native stdout. Source bindings retain the original task request,
manifest, historical stdout/stderr and local read-only Cargo help/version. The
manifest enables default `full` features (pcap/etherparse) and does not disable
doctests. Historical successful output contains two unit tests followed by the
zero-test doc phase. Local Cargo 1.99.0 help documents `--no-fail-fast` and matches
the common-image Cargo version/commit; help/version queried no project tests or
builds. `root-policy-v5.json` and the plan bind the prior coordinator decision and
these exact identities before any native attempt.

Source/cache/image bytes, native commands, environment and resources are identical
to v3. Go's skip-at-any-depth rule and the OpenHands wrapper/i18n scope remain
unchanged. Cache audit flags remain false in their original draft receipts.
Qualified external audit dispositions and coordinator acceptance must reference
the **v5** plan hash; acceptance for an earlier plan cannot authorize this one.

Synthetic controls preserve accepted preflight failure with zero daemon calls,
exercise the entire fake driver for late rustdoc compile failure and valid unit
assertion failure, and reject wrong-prefix/module/duplicate IDs along with phase,
process and diagnostic counterexamples. These mock outcomes are clearly marked
synthetic and are not task outcomes. The retained historical success is recognized
as a data fixture only; no old task was rerun.

```sh
uv run python benchmarks/head-to-head/f05-offline-requalification-20261029/driver.v5.py verify
uv run python benchmarks/head-to-head/f05-offline-requalification-20261029/controls.v5.py
uv run ruff check --no-cache benchmarks/head-to-head/f05-offline-requalification-20261029
uv run ruff format --check --no-cache benchmarks/head-to-head/f05-offline-requalification-20261029
```

After independent review and explicit coordinator authorization, the interface is
`driver.v5.py run --task <frozen-id> --acceptance <external-file> --output
/tmp/dotrepo-f05-offline-requalification-<unique>`. This packet invokes no run.
Its accepted-preflight failure and native outcomes exist only in synthetic controls.

One inventory error is disclosed separately. The original v3 artifact manifest
accidentally included three generated `.ruff_cache` files. Later Ruff changed one
cache entry. All twenty substantive historical files and the original manifest
and freeze remain unchanged. `generated-cache-disposition-v4.json` preserves the
expected/observed cache hashes and limitation; no old hash was repaired. Current
inventories exclude `.ruff_cache` and `__pycache__`, and further Ruff calls use
`--no-cache`. The cache entry is not a source, oracle, plan, result or execution
input. Future verification must apply that explicit generated-cache disposition
rather than claiming all 23 original entries remain byte-identical.
