# Independent dependency preparation review — 2026-10-29

The three frozen cache drafts pass the bounded byte, package-origin, recorded
command and protected-alias audit described below. No actionable inconsistency
was found in the preparation packet. **Their audit flags remain false**; this
review does not promote descriptors or establish offline setup completeness,
common-image task equivalence, a qualified campaign, task completion or benefit.
Common-image absence claims remain bounded by construction provenance and visible
path controls rather than an exhaustive filesystem/credential-content inspection.

A separate synthetic review confirmed a pre-existing runtime JSON gold/oracle
alias gap. The coordinator's narrow amendment closes the reproduced cases at
runtime SHA-256 `43fa2f0a18802564934646db5fa80e75c0ced3856b07df8b72d5a27fda2b84c3`.
This is separate from the earlier source-link implementation review; its original
frozen runtime and receipts are unchanged.

## Frozen inputs and method

The preparation packet is `../f05-dependency-preparation-20261029/`, frozen by
`packet-freeze.json` SHA-256
`3888a19462854a37c20803fa9c62f525223af9f4f3d8aa9cfa2bf46affdd2f84`.
The worker handed off each immutable leaf before this reviewer read it. All 322
owned artifact hashes/lengths and the packet's top-level bindings matched.
[audit.py](audit.py) independently checks receipts, archives and package metadata;
[audit.json](audit.json) retains results. It never extracts or runs package/source
contents, imports the preparation driver/runtime or contacts Docker/a provider.
No package fetch, upstream command, network request or index/profile body read
was performed. This reviewer has prior development/source context, not fresh
blind or unfamiliar-agent context.

The coordinator supplied only protected-content hashes, retained unchanged in
[protected-content-digests.json](protected-content-digests.json), SHA-256
`a6da70671528ca633baaf2c343ce2787699b8554904bc9c064383ea1495a38f5`.
The set binds 51 files and 82 raw/canonical digests across gold/oracles, actual
oracle versions, snapshot artifacts and profile bodies. Future access/policy/
consumer/scorer artifacts do not yet exist and remain outside that set. No actual
hidden gold, oracle or profile body was read by this reviewer for this audit.

## Common image

The successful image ID is
`sha256:b47cd4a5061d271780bab25aa2637c2623dc675bd43380fc80cb65ec44e50092`.
`Dockerfile.v3`, plan v3, launchers, input image IDs, pre/post alias inspections,
build output and final inspect bind the observed construction. The recipe uses
`FROM scratch`, copies the known prior Rust image and selected Go/Node/uv tools,
and adds two owned npm launchers. It has no RUN, task-source copy, credentials,
VOLUME or ONBUILD declaration; the final explicit image environment is limited
to PATH/RUSTUP_HOME/CARGO_HOME/GOTOOLCHAIN/GOENV. Source-free construction is
supported by this retained input/recipe provenance, not by arbitrary image-name
trust. Prior source-free image preparation used official tool images, bounded
Debian package preparation and tool copies; no task source provisioning appears
in that input construction chain.

The native probe identifies Rust/Cargo 1.99.0, Node 24.22.2, default npm/npx
11.19.1, Go 1.27.3, uv 0.13.6 and required Rust system libraries on Linux ARM64.
It is a tool-availability control. The task-specific npm 11.12.1 is separately
installed in a temporary preparation prefix; that tooling tree is not exported.

The image's credential/path probe has explicit limits: it ran as UID 1000, so
negative existence tests beneath an unreadable `/root` do not prove those files
absent. Its `/workspace` and dependency-cache tests observe tmpfs overlays and
cannot inspect underlying image paths. Image inspect exposes configuration and
layer identities, not a complete filesystem inventory. These limitations do not
show a credential or task source was present. They mean those negative path
checks alone cannot justify exhaustive image-content absence claims. The packet
already calls this a candidate/tool control and disclaims exhaustive credential
inspection; no stronger live-readiness claim is supported here.

The first build's local-name registry resolution failure and second image's npm
symlink/launcher failure remain retained. The successful third build is bound to
its own recipe/image. No prior failure was counted as a success or silently
rebound.

## Per-cache evidence

Every cache was a plain regular-only archive under its declared download roots,
with no duplicate/traversal/link/device entries. All file hashes, normalized
modes/UID/GID/mtime, expanded/archive bounds, source revision/archive, common image,
script closure, plan, trace and descriptor hashes matched. Raw export regular
members have exactly the same names/content hashes as normalized cache members;
only directory headers and declared metadata normalization differ.

| Leaf | Files / expanded bytes | Independent package checks |
| --- | --- | --- |
| `rust-02-attempt-2` | 24,692 / 438,392,465 | 525 downloaded crate SHA-256 values match the pinned source Cargo.lock; 23,003 extracted crate members byte-match their distribution archives. The 525 additional `.cargo-ok` markers are Cargo metadata. |
| `typescript-02` | 2,562 / 213,726,697 | 1,281 content-store SHA-512 digests, 1,323 index-entry hashes and all referenced content objects match. Registry URLs are public npm HTTPS without credentials/query strings. 1,279 tarball URLs occur in the task lock; the only additional tarball is the explicitly pinned npm 11.12.1 tooling package. No sensitive authorization/cookie/API-key header names were retained in index metadata. |
| `go-03` | 2,832 / 63,513,466 | 27 module zip h1 sums and 45 go.mod h1 sums match pinned source `api/go.sum`; ziphash files agree. 2,648 extracted module members byte-match downloaded zips. No downloaded module zip was outside the source sums. |

The recorded commands are cargo fetch with `--locked --target
 aarch64-unknown-linux-gnu`, npm tooling install plus npm ci with `--ignore-scripts`,
and `cd api && GOWORK=off go mod download`. Captured configuration forces local Go
toolchains, disables Git credential prompting/global config and supplies no host
credential mounts. No source build/test or npm lifecycle hook invocation appears
in the executed command set. Rust's all-target first attempt failed at the cache
quota and remains retained; the native-target retry did not broaden bounds or
change the requested native task. Its plan subtracts the prior attempt from the
setup allowance.

One source npm lock entry, `@babel/runtime` 7.29.7, has no integrity value. Its URL
is source-bound and cache SHA-512 is internally validated, but a source lock
checksum comparison cannot be established for it. The initial review checker
incorrectly required equality to that null value; its failure is preserved in
[audit-initial-lock-check-stderr.txt](audit-initial-lock-check-stderr.txt) and
[npm-lock-integrity-mismatches.json](npm-lock-integrity-mismatches.json). The
checker now records the missing source integrity explicitly. This was a reviewer
assumption failure, not evidence of mismatched package bytes.

Protected raw/canonical checks found **zero nonempty matches** in all outer
members and regular files inside downloaded crate/npm/Go archives. Empty files
match the empty absent-profile digest innocuously and are counted separately;
they contain no hidden answer. Task-source digest comparisons likewise preserve
shared Apache licenses and empty files. The npm distributions additionally share
an OpenHands extension license/release configuration and MSW's distributed mock
service worker with the task tree. Their exact package origins are retained in
[npm-source-overlap-dispositions.json](npm-source-overlap-dispositions.json).
They are ordinary locked/public dependency distributions, not evidence that the
preparation copied the task checkout into cache. A blanket source-file hash deny
would wrongly reject them.

These observations support regular download origin and exclusion of preparation
build outputs/task checkout copies in the recorded process. They do not prove
semantic absence of every credential or encoded/partial hidden answer inside
arbitrary third-party distribution bytes. Exact/canonical alias checks are not
semantic or substring detection. Costs remain null; transfer counters are
container traffic, and all failed-attempt/setup/normalization work remains effort.

## Separate runtime gold/oracle amendment

At original runtime `f2f43560d85d2d1934b6f84bba26951d1cee81d8fe08e291c600a89754f850ab`,
`load_session` seeded hidden gold/oracle hashes with raw SHA only, while source
member checks compared raw plus canonical JSON. A noncanonical pretty original
and compact source reserialization therefore had different raw digests and the
source's canonical digest was absent from the deny set. Both synthetic gold and
oracle JSON became readable through README source bytes. Raw aliases rejected.

[gold_alias_control.py](gold_alias_control.py) and
[gold-alias-control.json](gold-alias-control.json) preserve that valid before
control. The historical script expects the old behavior and is not expected to
pass against the amended runtime. No actual empirical hidden body was used.
The coordinator's earlier independent fixture failure is not used as reproduction
evidence here.

The amended loader reads each already-bound gold/oracle artifact solely to add
`content_digests` on the host before source/cache admission. It does not expose
those bytes through requests, messages or tools. Independent after controls
[gold_alias_after_control.py](gold_alias_after_control.py) and
[gold_alias_other_task_control.py](gold_alias_other_task_control.py) reject all
eight raw/compact × gold/oracle × current/other-task cases before backend/provider
use. Their separate receipts bind the amended runtime hash; the source-link
qualification's old runtime snapshot is preserved. This closes the reproduced
raw/canonical alias gap and does not claim general semantic leak prevention.

## Remaining gates

No flag was changed or qualification minted. Any qualified cache descriptor must
be a new explicit decision bound to these exact bytes, the accepted audit scope
and final protected artifacts. Common-image task/environment equivalence and full
unchanged native test/oracle requalification remain separate. npm offline tooling
restoration, ignored-hook equivalence and actual offline completeness remain
unestablished. This review authorizes neither a campaign nor provider calls.
