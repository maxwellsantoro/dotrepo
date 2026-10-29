# Go-01 single download-only result

The one coordinator-authorized attempt completed as
`download-cache-retained-unqualified`. The unchanged frozen plan and driver
executed npm ci --ignore-scripts at repository root, then go mod download in tsc
and tools. Every command exited zero. No lifecycle scripts, compilation, go
install, native collection/tests, providers or models ran; no retry occurred.

The cache contains 15,246 regular files, 351,962,210 expanded bytes and a
366,622,720-byte normalized plain tar. SHA256 is
583fad501fa7b1a1a6d85ab8fe4b890786e39c1e016f785d6d3fb9d060383284.
Both raw transport and normalized archive stay outside Git at the exact authorized
scratch directory `/private/tmp/dotrepo-go01-dependency-download-cache-20261029-1/`.
Inventory, provenance, raw bounded logs, authorization and receipts are retained
here; `summary.json` reports root-level byte/file totals without treating those
counts as content qualification.

Preflight took 2.421 seconds, downloads 15.516 seconds, total work 29.434 seconds
and cleanup 0.549 seconds (total elapsed 29.983 seconds). The frozen limits were
900 seconds plus 60 seconds cleanup, 3 CPUs, 4 GiB memory/equal swap, 256 PIDs,
8 GiB executable workspace, 1 GiB cache and 512 MiB transport. Container interface
counters measured 171,425,424 received and 1,121,785 sent bytes, including protocol
and incidental traffic. Dollar cost is unknown and remains null.

Pinned source bytes, stdin archive hash and tool versions were checked. Original
tracked source hashes still matched after downloads. Networking was disconnected
and absent from inspect before export. Only npm-cache/_cacache and go/pkg/mod
were exported; the bounded packer admitted regular-only safe paths. The 24 driver
daemon receipts include cleanup, post-removal inspect and responsive owned-name
listing. A separate read-only host inspect/list (two additional daemon calls)
confirmed absence after driver completion. This is Linux ARM64 container execution
on macOS, not native Linux-host or x86 validation.

The source/image/plan/cache descriptor remains a draft: all audit flags are false.
Exact known protected-alias screening is not semantic content or credential audit.
Independent cache audit, npm hook equivalence, native collection, proposed oracle
exclusion policy and full native wrapper task qualification remain separate gates.
The npm output included an informational newer-version notice; no update ran.

`verify_result.py` performs read-only integrity checks against retained receipts,
source stream, plan/auth bindings, cache archive, inventory and absence. Run with
`uv run --offline --no-sync python <absolute-path>/verify_result.py`. It makes no
daemon/network/native calls. Its initial inventory-key assumption was corrected
from size to the existing bytes contract; the harness-only failure is disclosed
in verification-harness-correction.json and did not trigger a workload rerun.
Ruff check and format checks passed with --no-cache.

Earlier preparation plans, oracle/source evidence and image/cache packets were
not modified. This packet establishes successful download preparation within its
bounds; it does not establish native task completion or consumer benefit.
