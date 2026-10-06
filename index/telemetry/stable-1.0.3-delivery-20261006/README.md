# Published stable 1.0.3 delivery — October 6, 2026

[The delivery receipt](delivery.json) separates source validation, actual asset
and six-crate publication, MCP registry recovery, installation controls and
pending public archive continuity. The release source is immutable commit
`9af41e8bda5fa30f271f9bdd5e8d19dd41e6eb2d` at `v1.0.3`.

The downloaded macOS ARM bundle and a fresh locked crates.io CLI installation
each passed 27 controlled safety checks. The bundle also passed CLI/public-query/
MCP/LSP help and MCP/LSP stdio controls asserting server version 1.0.3. All seven
published assets match their GitHub digests; both binary bundles and the MCPB
also match their published checksum files. All six crates match their exact
Cargo version, clean VCS source commit and official download checksum.

The tagged release workflow's assets and crates jobs succeeded, but its registry
job rejected the older 205-character description. Recovery run `37419332368`
published the existing MCPB using main's bounded metadata template. A subsequent
live API read confirmed active latest 1.0.3 and the exact published MCPB checksum.
No tag was moved and no asset was overwritten. The maintenance template fix is
merged separately in [PR #144](https://github.com/maxwellsantoro/dotrepo/pull/144);
its exact-head and merged-tree `ci-gate` checks passed. The release tag still
points to its original source.

The stable patch preserves schema and Rust API compatibility. It adds bounded
regular-file import reads, no symlink traversal, conservative Rake declarations,
and forced-import symlink/shared-hardlink refusal. Development context metadata
and newer network-target policies remain outside this release. Full local Ruff
format checking still reports 47 unchanged historical Python files; the retained
baseline hashes distinguish that existing limitation from changed-file checking.

[The installation receipt](receipt.json), [bundle controls](bundle-safety.json),
[registry-install controls](registry-safety.json), [live registry response](registry-1.0.3-latest.json)
and logs preserve exact observed outcomes. `delivery.json` binds retained copies
by SHA256. Their recorded commands retain original local output paths; archived
copies use the same basenames. Frozen executed stdio sources add `.txt` so
formatting checks do not rewrite their observed bytes. Binary payloads and the Cargo target cache are not
committed here.

To repeat the publication checks on macOS ARM while 1.0.3 is still latest:

```bash
uv run python index/telemetry/stable-1.0.3-delivery-20261006/verify_publication.py \
  --expected-commit 9af41e8bda5fa30f271f9bdd5e8d19dd41e6eb2d \
  --output-root /tmp/dotrepo-published-1.0.3-repeat \
  --cargo-target-dir /tmp/dotrepo-published-1.0.3-cargo-target
```

Use a new output root; preserve unsuccessful attempts. This verifier retrieves
public artifacts and performs a fresh locked installation, without publishing or
changing cloud state. It requires the then-current latest stable version to
remain 1.0.3. Linux artifacts were hash-checked, not executed on this macOS host.

Cloudflare R2 account enablement, historical backfill and archive-backed public
deployment remain pending. These installation checks do not establish public
history continuity, independent adoption or downstream task benefit. The earlier
release and public-project study packets remain unchanged.
