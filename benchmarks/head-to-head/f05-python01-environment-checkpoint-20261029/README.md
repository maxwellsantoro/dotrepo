# Python01 source-free environment checkpoint

One owned probe observed the existing frozen image's uv 0.13.6 and CPython
3.11.2 on Linux ARM64, with ABI `cpython-311-aarch64-linux-gnu`. The interpreter
used isolated/no-site mode, image-only import paths and no unexpected Python
configuration variables. Script and tool hashes matched before and after.
The attempt took 2.750345 seconds, including 0.195568 seconds of cleanup;
same-attempt removal and absence receipts passed. Preparation cost remains null.

The [integration manifest](integration.json) binds seven byte-preserved packets:

- [Source-grounded environment plan](../f05-python01-environment-plan-20261029/README.md)
  and [independent plan review](../f05-python01-environment-plan-review-20261029/report.json).
- [Owned probe driver](../f05-python01-probe-driver-20261029/README.md)
  and [independent driver review](../f05-python01-probe-driver-review-20261029/report.json).
- [Consumed one-attempt authorization](../f05-python01-probe-authorization-20261029/authorization.json),
  [actual result](../f05-python01-probe-result-20261029/result.json)
  and [independent raw-result review](../f05-python01-probe-result-review-20261029/report.json).

The driver review passed 26 copied and seven independent fake controls before
the one actual attempt. All 16 actual command receipts and raw streams are
retained. The reviewed transport has a bounded client-reaping tail; work beyond
the 60-second stage allowance would remain incomplete. The 900-second shared
preparation allowance must carry forward the 2.554778 seconds of observed probe
work, with cleanup accounted for separately.

Only the owned probe script was provisioned. No repository source, dependency,
gold, profile or credential payload entered the container. This observation
supports a separately reviewed locked-wheel preparation step. Dependency
compatibility, cache reuse, imports, native collection, phase/capture joins,
oracle qualification and campaign admission remain open. It supplies no
consumer-benefit evidence and changes no frozen task or evaluation split.

The original manifests, payloads and local execution paths are preserved. The
live adapter requires its original retained helper/environment bindings; it is
not a portable public runner. The source archive remains external and explicitly
excluded from this integration. Local verification below checks retained byte
bindings only; it neither executes the adapter nor assesses source completeness:

```bash
uv run python - <<'PY'
import hashlib
import json
from pathlib import Path

root = Path("benchmarks/head-to-head/f05-python01-environment-checkpoint-20261029")
manifest = json.loads((root / "integration.json").read_text())
for packet in manifest["packets"]:
    base = root.parent / packet["path"]
    raw = (base / "FREEZE.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == packet["freezeSha256"]
    for name, binding in json.loads(raw)["artifacts"].items():
        data = (base / name).read_bytes()
        assert len(data) == binding["bytes"]
        assert hashlib.sha256(data).hexdigest() == binding["sha256"]
print("Seven retained packet closures match; no execution performed")
PY
```
