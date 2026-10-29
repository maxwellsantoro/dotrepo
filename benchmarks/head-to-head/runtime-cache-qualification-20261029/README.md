# Frozen download-cache copy controls, 2026-10-29

The first contained task qualifications needed downloaded dependencies before
offline execution. The internal runtime now supports an explicitly frozen warm
condition alongside its original cold condition. This packet checks that bridge
with owned fixture bytes and no provider or third-party code execution. It does
not qualify a real dependency cache, task, common image, provider, campaign, or
consumer benefit.

A warm configuration binds a per-task regular-file archive, recursive inventory,
provenance, preparation script and trace. The preparation receipt binds the exact
image, source revision/archive, cache archive, script and trace; it declares tool
versions, limitations, explicit nullable preparation cost, and audit claims about
download-only preparation and excluded build output, task checkout and
credentials. The host checks these bindings before a session starts. It also
rejects traversal, links/devices, hash/inventory mismatches, paths outside the
download-cache roots, excessive combined source/cache bytes, and exact aliases
of hidden gold, protected profiles/access artifacts or the task source archive.

These checks establish consistency, not the truth of audit claims. They do not
semantically classify every member, prove absence of secrets, or reject every
file whose bytes also occur in the task checkout. Empty files and shared license
texts can legitimately match dependency files. Independent inspection of the
actual cache inventory/provenance remains required before a live qualification
flag can be set. Lifecycle-disabled dependency installation is not automatically
equivalent to the upstream installation procedure.

Each session receives a fresh private copy under
`/workspace/dependency-cache` before any provider request. It shares no writable
mount with another session. A failed copy stops before a provider call and still
cleans up. Cold sessions reject nonempty dependency-cache configuration.
Preparation and maintenance costs remain unallocated nulls in session receipts;
campaign accounting must retain and allocate the actual work separately.

`copy-control-001.json` records two real Docker sessions with owned fixture
bytes. Each starts with the same cache bytes, mutates its own copy, and removes
its container. The second session sees the original bytes, demonstrating no
mutable carryover from the first. Seeding leaves a pre-clone workspace without
task source. Cleanup is independently checked through Docker inspect. The
historical runtime snapshot was recovered by removing the later source-archive
alias denial line and verified against the receipt's exact runtime hash.

`copy-control-002.json` repeats these controls against the final retained
`runtime.py.txt`, including that denial. The driver and runtime hashes match the
receipt. The image is the same pinned backend-control image described in the
[earlier control packet](../runtime-qualification-20261029/README.md), with
synthetic qualification flags for this control only. No upstream cache was
seeded, no provider was called, and monetary costs are unknown. The focused
runtime/preparation suite passes 122 controls; those are apparatus checks.

To create a new observation with the retained image available locally:

```sh
uv run python benchmarks/head-to-head/runtime-cache-qualification-20261029/check_cache.py \
  --image sha256:8032a060e0198814ffe1868893bf89bdb02fa79f4de617873f23eb8dd3915af4 \
  --out /tmp/dotrepo-cache-copy-new-control
```

The driver imports the current checkout runtime. Verify its recorded hash
against the intended implementation; a future replay does not overwrite these
observations. `FREEZE.json` binds the files in this packet. Independent review
is retained separately under the operating-readiness packet's `runtime-review/`.
