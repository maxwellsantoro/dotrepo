# Go-only dependency projection 1: local data, unadmitted

This append-only packet materializes the exact scoped input declared by the
source-only collection proposal. It does not authorize native collection or admit
the cache, task or campaign. Original proposal, source, archive and false flags
remain unchanged.

The new tar is:

- Path: /private/tmp/dotrepo-go01-go-cache-projection-20261029-1/cache-go-only.tar
- SHA256: 76ea2bfa6725335b889d44fed07f40f6eeb804d124d683ad4f2c0a6a2607bcfd
- Transport: 292,392,960 bytes.
- Contents: 14,922 regular files; 278,162,103 expanded bytes.

Selection is exactly every declared regular parent member whose path starts
`go/pkg/mod/`. No npm subtree or Go build-cache root enters this derived input.
The full original cache is not provisioned through the new archive, so uninstalled
npm package payloads are also absent from it. This differs from merely omitting
npm ci while leaving the complete cache readable. No full-task dependency is
pruned/replaced: this is a new explicit collection-only input, preserving the
parent archive and the intended full-task normal npm setup.

BEFORE.json froze the script/input/declaration/output identities before the one
local derivation. Parent archive583fad50 and inventory900550d8 were rechecked.
The canonical selected path/content/byte/mode map matches
bf5aefaa56222f9337752edebddd50d2cfc4759ed8954f7f9f74bf3d70765131.

The trusted local program never extracts or invokes packages. It copies selected
member streams, checking every parent digest/length/mode against that declaration,
then rereads every derived member and compares the exact resulting map. Entries
are sorted by full path. Regular paths, content bytes and file modes are preserved;
uid/gid/mtime become zero and user/group names empty. POSIX PAX path metadata is
used only where needed. No directory records or synthesized dependency content
are added. Links, special/sparse/unsafe/duplicate paths and unknown selected
members fail. Plain output is capped at512MiB with a120-second local-work bound.

The derivation took3.132seconds and verified the parent archive unchanged after
completion. The original12 proposal bindings remain intact. Full inventory,
provenance, before record, result and ready-to-reference projection-spec.json are
retained; the tar stays outside Git. Ruff check/format passed with --no-cache.
checks.json records interpreter identity and verification results. No failure or
retry occurred.

Path/byte projection does not certify that every Go-module file is text: public
module fixtures and download metadata retain their inherited audit/source-role
limitations. It creates no build cache and no new native compiler/helper outcome.
Public JS6 reference-library and native7 packaging roles remain distinct for the
future full task. Independent cache/source-scope review, no-eager-npm collection
adjudication, bounded runner review, native context binding and separate explicit
authorization remain required.

No daemon, network, Go, Cargo, package/source code, native task, provider or model
execution occurred. Only trusted local uv/Python tar/hash data operations ran.
Dollar cost remains unknown/null. CacheGloballyQualified, nativeTaskAdmitted and
campaignAdmitted all remain false. Stop here for independent review.

The retained derivation command was:

```
uv run --offline --no-sync python benchmarks/head-to-head/f05-go01-next-qualification-20261029/go-only-projection-1/derive.py --output-root /private/tmp/dotrepo-go01-go-cache-projection-20261029-1
```

The command records completed local data work; its exclusive outputs must not be
reused or overwritten. No native runner is implemented by this packet.
