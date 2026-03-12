# Public export examples

These examples use the real exported public JSON tree rather than a separate
demo API.

## 1. Generate a local export

```bash
cargo run -p dotrepo-cli -- public export \
  --index-root index \
  --out-dir public \
  --generated-at 2026-03-10T18:30:00Z \
  --stale-after 2026-03-11T18:30:00Z
```

## 2. Read snapshot metadata and repository count

```bash
python3 - <<'PY'
import json
from pathlib import Path

meta = json.loads(Path("public/v0/meta.json").read_text())
inventory = json.loads(Path("public/v0/repos/index.json").read_text())
print("api version:", meta["apiVersion"])
print("snapshot digest:", meta["snapshotDigest"])
print("repositories:", inventory["repositoryCount"])
PY
```

## 3. List repository summary and trust paths

```bash
python3 - <<'PY'
import json
from pathlib import Path

inventory = json.loads(Path("public/v0/repos/index.json").read_text())
for entry in inventory["repositories"]:
    repo = entry["identity"]["repo"]
    summary = entry["links"]["self"]
    trust = entry["links"]["trust"]
    print(f"{repo}: {summary} | {trust}")
PY
```

## 4. Inspect one repository summary

```bash
python3 - <<'PY'
import json
from pathlib import Path

summary = json.loads(
    Path("public/v0/repos/github.com/sharkdp/fd/index.json").read_text()
)
print(summary["identity"])
print(summary["repository"]["description"])
print(summary["selection"]["reason"])
PY
```

## 5. Agent-style traversal from inventory to trust

```bash
python3 - <<'PY'
import json
from pathlib import Path

root = Path("public/v0")
inventory = json.loads((root / "repos/index.json").read_text())

for entry in inventory["repositories"]:
    identity = entry["identity"]
    trust_path = entry["links"]["trust"].removeprefix("/v0/")
    trust = json.loads((root / trust_path).read_text())
    print({
        "repo": f'{identity["host"]}/{identity["owner"]}/{identity["repo"]}',
        "selection": trust["selection"]["reason"],
        "recordStatus": trust["selection"]["record"]["record"]["status"],
    })
PY
```

These examples should work equally well against a local export or the CI
artifacts once extracted.
