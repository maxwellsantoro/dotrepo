# Faithful source links — bounded provisioning qualification

This packet qualifies the minimal private F-05 source-bundle extension needed by
the 17 symlinks actually retained in the next-eight source archives. It changes
source provisioning, not repository task scope, gold, the index, models or the
public dotrepo protocol. All prior frozen source/runtime packets remain unchanged.

The runtime now accepts an optional exact `symlinks` map beside the existing
regular-file inventory. Each entry binds the normalized member path to the
unchanged UTF-8 target text, target SHA-256, Git blob SHA and mode `120000`.
Regular-only inventories remain accepted, and `load_session` still returns six
values. The runtime code remains in its original module, covered by the existing
`runnerSha256` binding. Provenance validation checks consistency; it does not
authenticate upstream provenance assertions or independently recompute a Git tree.

Admission validates the complete logical namespace before any Docker/provider
operation. It rejects absolute/drive/backslash/control targets, root escapes,
dangling links, chain/hop cycles, directory-alias cycles, members beneath links or
regular-file ancestors, duplicate/conflicting definitions, hardlinks/devices/FIFOs,
unsafe permission bits and mismatched target hashes/bytes/mode. `..` is processed
after preceding link components resolve, rather than relying on lexical cleanup.
The minimum bounds are 1,024 links, 4,096 UTF-8 bytes per target/path, 200,000
archive/logical members, 40 link hops, and the existing source/archive workspace
byte bound including target bytes. Final targets must be retained regular files
or explicit/implicit directories. This intentionally rejects some otherwise
possible POSIX link topologies; it is not a general filesystem service.

No upstream link is created or followed on the host. `read_upstream` keeps regular
reads unchanged, lists typed members when links exist, and returns bounded link
metadata for a link path. It does not dereference the link or walk directory
aliases on the host. The existing hidden-gold/access/profile content checks still
apply to every regular source member and to retained link-target bytes.

Checkout refuses an already existing destination, including a partial prior
checkout. For bundles with links it creates two derived transport tars: validated
regular files/directories, then actual symlinks. Original archive bytes and link
identities remain intact. Tar member metadata and executable modes are preserved
through transport; existing nonroot ownership/umask extraction policy remains.
`sourceCopy` receipts bind the original archive hash, both transport hashes and
stdin byte counts. Effort uses the submitted transport bytes, including the extra
tar padding. These counts describe bytes submitted to Docker stdin, not a claim
about every byte consumed after a failed process or bytes written on disk.
Dependency caches remain strictly regular-only, with both admission and backend
seed guards; source-link support cannot enable cache links.

## Retained checks

- **116 focused runtime tests passed.** They include all previous runtime controls,
  all 17 actual path/target identities in contained fixture namespaces, chain-plus-
  `..` escape despite lexically contained spelling, cycles/dangling links, ancestor
  writes in both archive orders, target/blob/mode drift, hidden-content aliases,
  duplicates/hardlinks/devices/FIFOs, cache refusal, six-value loading, bounded
  metadata reads and transport-byte accounting.
- The complete retained Home Assistant archive admitted **30,200 regular files and
  three links**. The complete Deepseek archive admitted **19,863 regular files and
  14 links**. Exact original archive, regular inventory, details and provenance
  hashes are bound in [qualification.json](qualification.json). The new inventory
  copies add link metadata without changing archive bytes or old frozen files.
- Two fresh real Docker containers passed the final owned fixture control with
  image `sha256:8032a060e0198814ffe1868893bf89bdb02fa79f4de617873f23eb8dd3915af4`.
  `readlink` preserved targets including a trailing slash; reads/writes followed
  actual contained aliases; executable mode `755` and UID `1000` were observed.
  The second container saw original fixture bytes after the first mutated its
  private alias. Both refused a second checkout, had only tmpfs mounts, network
  `none`, readonly roots and independently confirmed absence after cleanup.
- Each final fixture checkout submitted **20,480 bytes** across two transport
  archives versus the original **10,240-byte** archive. Hashes and operations are
  retained. No upstream source was provisioned into these containers or executed;
  only owned fixture data and basic shell/read/stat controls were used.
- Ruff check/format and `git diff --check` passed for the owned implementation.

[before.json](before.json) binds the pre-edit source and actual-link proposal.
[actual-links.json](actual-links.json) preserves the 17 motivating identities.
`qualification-001.json` and `qualification-002.json` retain earlier passing
controls against the first implementation; the first used the platform's default
temporary directory, which was removed, before the driver was corrected to use
explicitly owned `/tmp`. `driver-001.py.txt` and `runtime-control-001.py.txt` bind
those exact executions. `qualification-003.json` retains the next passing version
before the final C1-control-character refusal; `runtime-control-003.py.txt` binds
it. The final [qualification.json](qualification.json) matches the final runtime
and driver hashes. None of these earlier receipts is silently promoted to cover
later source changes. An initial new loader test failed because its synthetic
campaign omitted the existing required profile/absence response object; the
fixture was corrected before the final 116-test pass.

The new full-archive admission controls use an empty hidden-hash set deliberately:
they establish structural/source-byte admission only. Existing focused loader
controls separately verify protected-content rejection before backend use. A live
campaign still requires its actual hidden artifacts, bound runtime, qualified
environment/cache/resources/provider, skip/oracle decisions and independent review.
This packet does not remove those gates, authorize model calls, or establish task
completion or consumer benefit. No upstream code, network acquisition, Docker
build, Cargo check or paid provider was run for this packet.

[checks.json](checks.json) and [freeze.json](freeze.json) bind the exact implementation,
patch, new inventories and observations. The driver can reuse original retained
archives from `/tmp` and records fresh outputs; do not rerun it over this frozen
packet. Use a copied/new output packet for subsequent qualification.
