# Public export examples

These examples show how to consume the dotrepo public JSON tree. The hosted
deployment at `https://dotrepo.org/` is the current primary consumption path;
the same tree can also be inspected locally, from CI artifacts, through the
local same-origin hosted-query runtime, or through the `workers.dev` staging
origin when needed.

## 1. Fetch hosted snapshot metadata

```bash
# Replace BASE_URL with the current hosted public URL (for example
# https://dotrepo.org today)
curl -s "$BASE_URL/v0/meta.json" | uv run python -c "
import json, sys
meta = json.load(sys.stdin)
print('api version:', meta['apiVersion'])
print('snapshot digest:', meta['snapshotDigest'])
print('generated at:', meta['generatedAt'])
"
```

## 2. List repositories from the hosted inventory

```bash
curl -s "$BASE_URL/v0/repos/index.json" | uv run python -c "
import json, sys
inventory = json.load(sys.stdin)
print('repositories:', inventory['repositoryCount'])
for entry in inventory['repositories']:
    repo = entry['identity']['repo']
    print(f'  {repo}: {entry[\"links\"][\"self\"]}')
"
```

## 3. Generate a local export

For local review or development:

```bash
cargo run -p dotrepo-cli -- public export \
  --index-root index \
  --out-dir public \
  --generated-at 2026-03-10T18:30:00Z \
  --stale-after 2026-03-11T18:30:00Z
```

## 4. Read local snapshot metadata and repository count

```bash
uv run python - <<'PY'
import json
from pathlib import Path

meta = json.loads(Path("public/v0/meta.json").read_text())
inventory = json.loads(Path("public/v0/repos/index.json").read_text())
print("api version:", meta["apiVersion"])
print("snapshot digest:", meta["snapshotDigest"])
print("repositories:", inventory["repositoryCount"])
PY
```

## 5. Inspect cache validators and changed files

```bash
uv run python - <<'PY'
import json
from pathlib import Path

meta = json.loads(Path("public/v0/meta.json").read_text())
files = json.loads(Path("public/v0/files.json").read_text())
print("etag:", meta["validators"]["etag"])
print("files:", files["fileCount"])
for entry in files["files"][:5]:
    print(entry["path"], entry["sha256"])
PY
```

## 6. Inspect one repository summary locally

```bash
uv run python - <<'PY'
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

## 7. Agent-style traversal from inventory to profile

```bash
uv run python - <<'PY'
import json
from pathlib import Path

root = Path("public/v0")
inventory = json.loads((root / "repos/index.json").read_text())

for entry in inventory["repositories"]:
    identity = entry["identity"]
    profile_path = entry["links"]["profile"].removeprefix("/v0/")
    profile = json.loads((root / profile_path).read_text())
    print({
        "repo": f'{identity["host"]}/{identity["owner"]}/{identity["repo"]}',
        "purpose": profile["purpose"],
        "status": profile["trust"]["selectedStatus"],
        "hasDocs": profile["completeness"]["hasDocs"],
    })
PY
```

## 8. Agent-style traversal from inventory to trust

```bash
uv run python - <<'PY'
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

## 9. Query one field locally from the same index snapshot

The static export ships summary, profile, and trust JSON files. It does not
precompute arbitrary query-path files. For local query access, either use
`dotrepo public query` directly or run `dotrepo-public-query` against the
exported tree when you want same-origin hosted-query review:

```bash
cargo run -p dotrepo-cli -- public query github.com sharkdp fd repo.description
```

## 10. Batch profile and field lookup

```bash
cargo run -p dotrepo-cli -- public batch-profiles \
  --repo github.com/sharkdp/fd \
  --repo github.com/BurntSushi/ripgrep

cargo run -p dotrepo-cli -- public batch-query \
  --repo github.com/sharkdp/fd \
  --repo github.com/BurntSushi/ripgrep \
  --path repo.description \
  --path repo.test
```

Batch responses keep going when one repository or field is missing. Each result
contains either the normal response object or a machine-readable `error`.

Hosted batch lookup uses the same response envelope:

```bash
curl -s "$BASE_URL/v0/batch/profiles?repo=github.com/sharkdp/fd&repo=github.com/BurntSushi/ripgrep"

curl -s "$BASE_URL/v0/batch/query?repo=github.com/sharkdp/fd&path=repo.description&path=repo.test"
```

## 11. Serve a local same-origin public surface plus query route

```bash
cargo run -p dotrepo-cli -- public export \
  --index-root index \
  --out-dir public \
  --base-path /

cargo run -p dotrepo-cli --bin dotrepo-public-query -- \
  --index-root index \
  --public-root public \
  --bind 127.0.0.1:3000 \
  --base-path /
```

Then:

```bash
curl -s "http://127.0.0.1:3000/v0/repos/index.json" | uv run python -c "
import json, sys
inventory = json.load(sys.stdin)
print(inventory['repositories'][0]['links']['queryTemplate'])
"
```

These examples work against the current deployed public tree, a local export,
the local same-origin runtime, or extracted CI artifacts.

## 12. Search compact public profiles

```bash
cargo run -p dotrepo-cli -- public search \
  --q orbit \
  --status reviewed \
  --require-docs \
  --require-security-contact

curl -s "$BASE_URL/v0/search?q=orbit&status=reviewed&require-docs&require-security-contact"
```

Search results include compact profile fields, matched field names,
completeness signals, trust context, and links back to profile, trust, query,
and repository JSON.

## 13. Compare compact public profiles

```bash
cargo run -p dotrepo-cli -- public compare \
  --repo github.com/sharkdp/fd \
  --repo github.com/BurntSushi/ripgrep

curl -s "$BASE_URL/v0/compare?repo=github.com/sharkdp/fd&repo=github.com/BurntSushi/ripgrep"
```

Comparison responses are factual matrices: profile summaries, trust and
completeness signals, shared languages/topics, and side-by-side selected
statuses, confidences, licenses, and build/test/docs/security/license flags.
They do not rank projects or generate a recommendation.

## 14. Traverse declared profile references

```bash
cargo run -p dotrepo-cli -- public relations github.com sharkdp fd

curl -s "$BASE_URL/v0/repos/github.com/sharkdp/fd/relations"
```

The relations response reports declared `references` from the selected record.
When a referenced `host/owner/repo` exists in the same index, the response
includes a compact linked profile item and profile/trust/query links.

## 15. Measure known-repository lookup efficiency

```bash
uv run python scripts/build_public_lookup_workload.py \
  --public-root public \
  --limit 500 \
  --output /tmp/dotrepo-public-lookup-workload.json

uv run python scripts/measure_public_lookup_efficiency.py \
  --public-root public \
  --index-root index \
  --workload /tmp/dotrepo-public-lookup-workload.json \
  --output-json /tmp/dotrepo-lookup-efficiency.json \
  --output-md /tmp/dotrepo-lookup-efficiency.md
```

The benchmark reports task hit rate, field hit rate, compact public payload
bytes, and deterministic source/evidence proxy bytes. See
[`docs/public-lookup-efficiency-benchmark.md`](./public-lookup-efficiency-benchmark.md)
for interpretation notes.

## 16. Compare two public export manifests

```bash
uv run python scripts/diff_public_export_files.py \
  --old-files old-public/v0/files.json \
  --new-files public/v0/files.json \
  --output-json /tmp/dotrepo-public-file-delta.json \
  --output-md /tmp/dotrepo-public-file-delta.md
```

The delta report gives consumers the exact files to refetch from the new
snapshot and the byte ratio of that refetch set.

## 17. Measure public profile coverage

```bash
uv run python scripts/check_public_profile_coverage.py \
  --public-root public \
  --min-profiles 500 \
  --min-high-signal 500 \
  --output-json /tmp/dotrepo-profile-coverage.json \
  --output-md /tmp/dotrepo-profile-coverage.md
```

The coverage report counts exported `profile.json` files, marks profiles as
high-signal when they have a purpose, reviewed-or-better status,
medium-or-better confidence, and no selected-record conflicts, then lists the
lowest-signal profiles to improve next.
