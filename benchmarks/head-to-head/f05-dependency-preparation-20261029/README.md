# Common source-free image and bounded dependency preparation

This packet built one candidate Linux ARM64 Debian Bookworm image and retained
download-only caches for the same three tasks that had successful native outcomes
in the earlier four-task qualification packet. **No upstream test, source build
script, model or agent session ran here.** The new image has passed tool-availability
and download controls, not task requalification or all-twelve environment acceptance.

The candidate is
`sha256:b47cd4a5061d271780bab25aa2637c2623dc675bd43380fc80cb65ec44e50092`.
`common-image.json`, `Dockerfile.v3`, the input-image inspections and native tool
probes bind its actual bytes and construction. It copies only the already qualified
Rust/native-dependency image and Node/Go/uv image, using local aliases checked
against their exact full IDs before and after the build. There are no build `RUN`
steps, new installed packages, task sources, host mounts or credentials supplied
to the image. Two small source-free npm/npx wrappers invoke the exact copied npm
package by absolute path. Configuration has only PATH, RUSTUP_HOME, CARGO_HOME,
GOTOOLCHAIN and GOENV; no VOLUME or ONBUILD.

Native probes recorded Rust/cargo 1.99.0, Node 24.22.2, npm/npx 11.19.1, Go 1.27.3,
uv 0.13.6, Git 2.39.5, GCC 12.2.0, libpcap 1.10.3 and ALSA development package
1.2.8-1+b1. Complete Debian package inventory, actual environment and Linuxkit
kernel/ARM64 information are retained. This was Linux container execution on the
macOS host, not a native Linux host or x86 qualification. Known credential-path
controls and explicit configuration checks are retained; an exhaustive image
credential-content audit is not claimed.

| Unchanged task/source | Preparation | Retained regular files | Expanded cache bytes | Plain tar bytes | Successful setup seconds |
| --- | --- | ---: | ---: | ---: | ---: |
| rust-02 sniffnet `ab4bf739d46448436cb68933bb8260ee264449d5` | Locked Cargo fetch for native `aarch64-unknown-linux-gnu` | 24,692 | 438,392,465 | 463,104,000 | 6.206 |
| typescript-02 OpenHands `2875056f93d6eebcd887f64ae557258a7b0b0108` | Install pinned npm 11.12.1 to temporary tooling, then locked `npm ci`; all lifecycle scripts disabled | 2,562 | 213,726,697 | 217,098,240 | 27.979 |
| go-03 Vault `352089582444ea84feb03bc97eda97b35729e8ec` | API-module `GOWORK=off go mod download`, `GOTOOLCHAIN=local` | 2,832 | 63,513,466 | 65,812,480 | 1.918 |

Every preparation used a fresh nonroot container: 3 CPU, 4 GiB memory with equal
memory-swap limit, 256 PIDs, read-only root, all capabilities dropped,
no-new-privileges, private default PID/IPC namespaces, no host mount/socket or
credential environment. Workspace and temporary filesystems explicitly allowed
execution with nosuid/nodev. A separate hard 1 GiB tmpfs bounded each dependency
cache; all resident memory remained charged to the 4 GiB container. Source plus
cache was below 2 GiB and each plain cache archive below 512 MiB. Setup had a
15-minute task budget; the Rust retry deducted the entire earlier attempt's elapsed
time. Text traces were capped at 2 MiB per command. Binary archive transfer was
separately bounded at 512 MiB and streamed to scratch disk.

Only trusted package-manager download operations ran online. npm lifecycle hooks
were disabled, Cargo performed no compilation, and Go could not download another
toolchain. Containers were disconnected before export and removed afterward.
Exports contain only `cargo/registry/`, `go/pkg/mod/`, or `npm-cache/_cacache/`.
Checkout node_modules, temporary npm tooling installations, build outputs/caches,
package-manager logs and Cargo global-cache bookkeeping are excluded by the
declared export roots. No links or special entries occurred in the retained cache
archives. The packer would refuse them; it does not silently drop meaningful bytes.
File bytes are preserved; tar owner/time values are zero and modes are 644/755.

The full archives stay at
`/tmp/dotrepo-f05-dependency-preparation-20261029/<leaf>/cache.tar`, with leaf
`rust-02-attempt-2`, `typescript-02`, or `go-03`. Matching inventory, provenance,
preparation, trace, script and runtime-shaped `dependency-cache-spec.json` copies
exist beside each archive. The repository retains metadata and bounded raw traces.
Inventory/provenance bind the exact common image, source revision/archive, cache
bytes, plan, script closure and observed tool versions.

These descriptors deliberately **fail live runtime admission**. `downloadOnly` is
true from the recorded command protocol; `buildOutputsExcluded`,
`taskSourceExcluded` and `credentialsExcluded` remain false because independent
content/member and protected-evaluation-alias audits are pending. False means
unqualified, not a discovered inclusion. Do not mechanically flip the flags or
rewrite these frozen receipts after review; a later disposition/qualified receipt
must retain the original. Offline full-scope task requalification is also needed.
OpenHands needs an explicit frozen offline policy to install npm 11.12.1 from the
retained cache before using it; checkout node_modules/tooling were not exported.
Both campaign arms must eventually receive identical frozen cache/setup conditions.

All failures remain visible:

- Attempt 1: digest-qualified local names caused BuildKit to query public registry
  metadata and fail before COPY. No layers were acquired or task commands run.
- Attempt 2: image `ac1ef011...` built, but individual COPY dereferenced npm's
  launcher symlink and broke its relative module import. Rust/cargo/node probes
  passed before npm failed. That image remains tagged
  `dotrepo-f05-common-failed:20261029`; no task preparation ran on it.
- Rust cache attempt 1: untargeted locked Cargo fetch exceeded the hard 1 GiB
  cache quota while acquiring other-platform workspace dependencies, exit 101
  ENOSPC. The 11.794-second attempt and stderr are retained. The new frozen retry
  fetched the actual Linux ARM64 target under the same bounds and unchanged task
  scope. It did not narrow any native test command. Later offline qualification
  must establish whether the target-specific cache is complete.

The original plans, scripts, images and receipts are unchanged. No next-eight
setup/test work, profile/index access, provider call, VM change or campaign occurred.
The prior three successful task outcomes remain observations on their earlier
images; they do not transfer automatically to this common image.

`verify.py` independently checked all 454 prior frozen artifacts, new plan/script
bindings, cache bytes/inventories, source bindings, regular paths/permissions,
limits, offline container inspections and native receipt hashes. `packer_controls.py`
passed one positive and seven negative boundary controls. Ruff and format checks
passed for all nine owned Python files. Reproduction without a network or daemon:

```sh
uv run python benchmarks/head-to-head/f05-dependency-preparation-20261029/verify.py --output /tmp/dotrepo-dependency-preparation-new-checks.json
uv run python benchmarks/head-to-head/f05-dependency-preparation-20261029/packer_controls.py
uv run ruff check benchmarks/head-to-head/f05-dependency-preparation-20261029
uv run ruff format --check benchmarks/head-to-head/f05-dependency-preparation-20261029
```

Actual preparation commands are retained in the frozen plans and native receipts;
they use exclusive output paths and refuse reuse. Successful image construction
used `uv run python .../prepare.v3.py build`; caches used `prepare.v3.py prepare
--task typescript-02`, `prepare.v3.py prepare --task go-03`, and the append-only
`prepare.v4.py prepare --task rust-02`. Running them again requires new output
identities and a new freeze rather than overwriting retained evidence.

Known successful download traffic was 312,701,509 received and 1,852,791 sent bytes
from interface counters, including headers/incidental traffic. The failed Cargo
attempt has no post-download counter and its traffic remains unknown. Actual
per-command and per-attempt elapsed times are retained, including image failures.
Dollar costs remain null because no host/container/download meter was available;
unknown measurements are not zero. This packet demonstrates bounded tool and
dependency preparation, not applicable instruction establishment, complete task
outcomes or consumer benefit.
