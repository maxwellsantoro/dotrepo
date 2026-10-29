# F-05 remaining-eight source qualification proposal

This append-only packet acquires full source for the unchanged eight remaining
task identities and proposes the next execution work. **No task in this packet
has been executed or qualified.** No index/profile, importer output, provider or
model was consulted. The original F-05 source packet and first-four qualification
packet remain unchanged.

All eight exact commits were acquired using bounded bare Git object transfers.
No checkout, hooks, source filters, package installation or upstream program ran
on the host. Full tar/gzip archives and bare object databases stay under
`/tmp/dotrepo-f05-qualification-next8-20261029/<task>/`; this repository retains
inventories, Git identities, command receipts and the source excerpts needed to
review the proposal. These archives attest source revisions without fabricating
Git checkout metadata.

| Task | Original scope | Full tracked entries | Expanded bytes | Admission status |
| --- | --- | ---: | ---: | --- |
| rust-01 Tauri | Repository | 1,107 | 22,484,659 | Regular archive; aggregate coverage unresolved |
| rust-03 Iced | Repository | 597 | 8,788,452 | Regular archive; three-stage CI target identified |
| python-01 MiroFish | Repository | 128 | 9,064,963 | Regular archive; default/union adjudication pending |
| python-02 Home Assistant | `homeassistant` | 30,203 | 222,688,313 | Three tracked links; faithful provisioning pending |
| python-03 youtube-dl | `youtube_dl` | 981 | 6,945,071 | Regular archive; full suite/exclusions need qualification |
| typescript-01 Deepseek | Repository | 19,877 | 138,154,652 | Fourteen tracked links, including actual test fixtures |
| typescript-03 Vue | Repository | 703 | 6,521,634 | Regular archive; full five-project target identified |
| go-02 Beego | `client/cache` | 401 | 2,084,097 | Regular archive; three loopback services unqualified |

The total is 53,997 entries (53,980 regular files and 17 links), 416,731,841
expanded bytes. No Git submodules or missing LFS object bytes were found. Source
limits were 512 MiB compressed Git objects per task, 1 GiB expanded per task,
2 GiB expanded for the tranche, 128 MiB per file and 200,000 tranche entries.
Symlink targets are retained as tracked source bytes, not silently dereferenced,
removed or rewritten. `file-details.json` has separate regular `files` and
`symlinks` maps; `inventory.json` covers regular files. Runtime admission currently
requires the later faithful bounded link extension for the two affected tasks.

`execution-proposal.json` contains source-bound toolchain, setup, scope, oracle,
resource and cache proposals. Baseline bounds are one task at a time, 3 CPU,
4 GiB memory, 256 PIDs, 8 GiB workspace capacity, 900 seconds preparation and
1,800 seconds execution. Task-specific larger proposed ceilings are unapproved.
Moving `TMPDIR` under the workspace avoids the separate 512 MiB scratch ceiling;
all resident tmpfs and process memory still shares the container memory limit.
Deepseek's documented 8 GiB Node old-space ceiling is not measured minimum RSS.
Its proposed 12 GiB limit exceeds the current 8 GiB Docker VM and cannot run
without a later resource decision; a smaller bounded full-scope feasibility
attempt is also a possible later decision. No VM/global resource change occurred.

Dependency preparation and cache conditions must be measured and frozen separately
for identical use by both arms. No cache was built here. Exact source-free image
IDs, tool versions, browser/service dependencies, native test collections, expected
exclusions and executable oracle controls remain launch gates. Source-owned
mutable image/version aliases are observations, not frozen dependency identities.

The full intended test outcome may be a passing suite or complete native assertion
failure. Listing, setup/collection failure, interruption, missing scope or
unadjudicated skipped coverage is not completion. youtube-dl's expected source
exclusions must be frozen before execution; hardcoded SOCKS stand-ins are coverage
exclusions rather than proof of real proxy behavior. Unexpected skip/early-return
remains noncompletion. Default uncertainty does not automatically rule out a
source-grounded full union; the coordinator must adjudicate that alternative for
MiroFish and the Tauri Rust aggregate without narrowing or replacing tasks.

`independent-scope-review/` is exclusively the original curator's fuller-source
follow-up and explicitly discloses that history; its path name is not a claim of
a second independent review. `independent-challenge-review/` is a separate worker's
fresh challenge. Their artifacts are separately owned and are excluded from this
worker's final file inventory. The coordinator owns final disposition decisions.
No source-supported command is promoted to a complete portable instruction by this
planning packet.

`oracle-revision/` independently preserves the original Go oracle's nested-skip
false positive and an append-only corrected oracle. Synthetic controls pass
(3 positive, 11 negative); no previously qualified upstream tests were rerun.
The earlier Vault run had no skips at any depth, so its 93-test result remains
unchanged. Future Go qualification must reject skips at every test depth.

Verification can be repeated without a network or upstream execution:

```sh
uv run python benchmarks/head-to-head/f05-qualification-next8-20261029/verify.py --output /tmp/dotrepo-f05-next8-new-checks.json
uv run python -c "import runpy; print(runpy.run_path('benchmarks/head-to-head/f05-qualification-next8-20261029/oracle-revision/oracle.py')['controls']())"
uv run ruff check benchmarks/head-to-head/f05-qualification-next8-20261029 --exclude prerequisite-sources --exclude independent-scope-review --exclude independent-challenge-review
uv run ruff format --check benchmarks/head-to-head/f05-qualification-next8-20261029 --exclude prerequisite-sources --exclude independent-scope-review --exclude independent-challenge-review
```

The verifier checked all 215 original frozen artifacts, all eight tar/gzip hashes,
all source blob identities and complete Git Merkle roots, 48 transfer/parsing
receipts and retained prerequisite sources. Its local controls reject absolute,
parent, duplicate and unsupported-mode archive entries and detect tree content
changes. An initial development verifier assumed links shared the regular-file
map and raised `KeyError` on Home Assistant; that harness assumption was corrected
before the final successful checks. No source/artifact repair was needed.

`checks.json`, `report.json`, `packet-freeze.json` and `artifact-hashes.json` retain
the data-only check results and packet bindings. Local metered charge data and Git
transport byte totals were unavailable; costs remain null with explicit exclusions.
Archive/object/source sizes and command elapsed times are measured independently.
This is preparation evidence, not an agent campaign, task completion result,
execution validation or consumer benefit demonstration.
