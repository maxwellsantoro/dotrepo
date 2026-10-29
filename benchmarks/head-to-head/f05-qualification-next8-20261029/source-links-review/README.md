# Independent source-link runtime review — 2026-10-29

No actionable finding in the bounded source-link extension review at runtime
SHA-256 `f2f43560d85d2d1934b6f84bba26951d1cee81d8fe08e291c600a89754f850ab`.
This verdict concerns the inspected implementation and retained controls. It does
not qualify a live campaign, dependency cache, environment or upstream task.

The source qualification input is `../source-links-qualification/`, freeze SHA-256
`467a8de48c814ca66b4570bf51e65e65f03b484c92eaf6a14cf9bf663a5e7d33`.
All 16 bound files, current runtime/test hashes and final driver binding matched.
The implementation diff was inspected against the prior regular-only runtime.
The reviewer previously assessed the source-link proposal and source inventories;
this is an independent implementation review with that context, not fresh blind
qualification. No original/frozen source, runtime, tests or upstream file changed.

## Executed independent checks

- `uv run pytest scripts/tests/test_agent_runtime.py -q`: **116 passed**; exact
  output retained in [focused-tests.txt](focused-tests.txt). These cover earlier
  protected-gold/profile/archive aliases and loader failures as well as the new
  link controls. The loader retains its six-value return contract and old regular
  inventories; dependency caches refuse links at admission and backend seeding.
- [review_controls.py](review_controls.py) passed with no Docker/provider/network
  access. Its counterexamples accept a contained directory chain with `..` after
  link resolution and a sibling alias. They reject trailing slash/dot/dotdot
  traversal through a regular file, root/ancestor aliases, a three-directory alias
  cycle, chained root escape, members below links, and duplicate directory entries.
- Mocked mkdir, first-transport and second-transport failures retained failure
  outcomes and counted zero, one or two actually submitted archives respectively.
  Transport SHA-256 and byte-count receipts matched submitted data. Existing-path
  refusal uses non-recursive `mkdir`, so even partial previous checkout is refused;
  neither phase merges into a model-created prior namespace.
- The exact complete retained Home Assistant archive statically admitted 30,200
  regular files and three links; Deepseek admitted 19,863 regular files and 14
  links. Archive hashes match original acquisition metadata. These checks used
  empty protected-content sets to isolate structural admission, created no host
  source links and performed no extraction or upstream execution. Actual campaign
  admission still requires its actual protected artifacts.
- Retained final owned Docker receipts were independently checked against raw
  inspect/operation entries: exact image, UID 1000, readonly root, network none,
  capabilities dropped, no-new-privileges, no host mounts, only declared tmpfs
  roots; fresh fixture bytes and exact `readlink` output; second checkout refused;
  20,480 submitted transport bytes; cleanup and subsequent absence. This reviewer
  made no new daemon calls. The receipts establish owned fixture behavior, not
  full-archive execution.

[controls.json](controls.json) retains the checks and exact actual archive hashes.
The counterexample program is rerunnable offline with:

```sh
uv run python benchmarks/head-to-head/f05-qualification-next8-20261029/source-links-review/review_controls.py
```

## Implementation boundaries assessed

`source_link_targets` resolves each POSIX component in the full logical tree.
It processes link expansion before a following `..`, requires directory traversal,
bounds hops and separately detects recursive directory-alias namespaces. Ancestor
validation rejects files/directories below a link regardless of tar order. Exact
inventory target text, target hash, Git blob SHA, Git mode and effective tar link
name must agree; undeclared links, hardlinks/devices/FIFOs, conflicts and duplicates
are refused. This is a deliberately restricted subset of POSIX topologies.

`source_read` returns typed, caller-bounded metadata for links and regular source
bytes for regular paths. It does not dereference links on the host or expose
unvalidated alias children. The target metadata and all regular source contents
remain subject to protected-content checks. Those checks enforce exact/raw and
canonical JSON aliases, not semantic secret detection or provenance authenticity.

`DockerBackend._extract` refuses an existing destination, then transports regular
members/directories before links. No regular member can write through an admitted
link namespace. Both phase hashes and original archive hash are retained; source
and cache accounting uses submitted stdin bytes, including tar padding. This
measures bytes submitted, not necessarily consumed or successfully written after
failure. Elapsed session time includes transport construction and failure overhead.
No token/cost or task outcome is inferred from provisioning success.

The two arms use the same source admission/checkout implementation. Pre-clone
source-first access remains bounded source reads or explicit checkout before shell;
typed link metadata supplies source facts rather than profile/gold access. Warm
cache support stays separate and regular-only. Audited cache exclusions and image
qualification remain external requirements; all-true audit assertions do not prove
absence of arbitrary task source, credentials or secrets.

## Limits

The full archives were read statically only. No upstream command, source tree,
model/provider API, package install, Docker build or network request ran. No new
real Docker control was necessary because retained owned receipts and offline
phase/failure controls covered the changed provisioning path. This review does
not establish downstream test completeness, tool availability, native task oracle
correctness, actual environment/cache readiness, consumer applicability or benefit.
The original qualification correctly leaves those gates separate and preserves
prior receipts rather than rebinding them to changed runtime code.
