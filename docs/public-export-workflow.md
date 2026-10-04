# Public export workflow

This doc covers the operator and reviewer loop for the read-only public JSON
tree and its hosted deployment.

## Inputs and outputs

Generate the read-only JSON tree and website from `index/` and the checked-in
fixture contracts. [Public architecture](public-surface.md) owns capabilities and
runtime bounds; [public examples](public-export-examples.md) owns routes.

```text
public/
  index.html, docs/, repositories/, writing/
  query-input/<host>/<owner>/<repo>.json
  v0/
    meta.json, files.json, stats.json
    repos/{index,search}.json
    repos/<host>/<owner>/<repo>/index.json, profile.json, trust.json, relations.json
    snapshots/log.json
    snapshots/<snapshotId>/files.json, repos/, query-input/
```

`public/`, `release-gate/`, and `dist/` are gitignored review outputs.
Private `query-input/` powers the runtime and is blocked from public serving.
CI review artifacts have bounded retention; deployed immutable history belongs
in the separately provisioned archive.

Agents working on fixtures, runtime routes, and presentation can proceed in
parallel with separate output roots. One coordinator runs the integrated gate
and owns deployment after source, contract, and freshness evidence agree.

## Local review loop

### 1. Fixture and golden-output regression gate

The smallest review surface lives under:

- `crates/dotrepo-core/tests/fixtures/public-export/fixture-index/`
- `crates/dotrepo-core/tests/fixtures/public-export/expected/public/v0/`
- `crates/dotrepo-core/tests/public_export_fixture_pack.rs`

Run:

```bash
cargo test -p dotrepo-core --test public_export_fixture_pack -- --nocapture
```

That test fixes `generatedAt` and `staleAfter`, recomputes `snapshotDigest` from
the checked-in fixture index, and compares the exported `meta.json`,
`files.json`, bundle-level `repos/index.json`, per-repository `index.json` /
`profile.json` / `trust.json`,
and repo-scoped `query-input/*.json` files byte-for-byte against the checked-in
golden tree.

Use this when reviewing response-shape changes, claim-visibility changes, link
changes, or artifact-path changes.

For the additive-only `v0` compatibility contract around required keys, links,
and error codes, see [`docs/public-api-compatibility.md`](./public-api-compatibility.md).
RFCs 0016 through 0019 serve as the accepted `v0` launch docs for that surface.
For the canonical freshness definitions used by exports and individual
records, see [`docs/public-freshness.md`](./public-freshness.md).

### 2. Deterministic local export from the real index

For review artifacts outside the fixture pack, use fixed timestamps so repeated
runs on the same input stay byte-stable. These historical review timestamps do
not refresh source facts or satisfy the current-time record freshness gate:

```bash
cargo run -p dotrepo-cli -- public export \
  --index-root index \
  --out-dir public \
  --generated-at 2026-03-10T18:30:00Z \
  --stale-after 2026-03-11T18:30:00Z
```

Important details:
- `snapshotDigest` is recomputed from the checked-in `index/` inputs; ignored
  local crawler state does not perturb it
- `meta.json` is the sole mutable pointer and names the immutable snapshot paths
- `meta.json` publishes the retention contract: current+previous at the static
  edge, all published snapshots through archive, and append-only snapshot log
- the canonical `files.json` lists only immutable snapshot payloads with byte
  sizes and SHA-256 digests
- `v0/snapshots/log.json` records each published snapshot digest,
  `generatedAt`, repository count, and payload count
- `v0/stats.json` derives latest/history/delta instrumentation from that log
  and includes PageDigest economics for the current manifest: records covered,
  records needing fetch, records skipped, bytes covered, bytes avoided, and a
  coarse token-avoidance estimate
- mutable `v0/repos/` and `v0/files.json` copies remain compatibility surfaces;
  the Worker resolves them through the pointer with revalidation required
- deterministic mode changes freshness timestamps, not response semantics
- ordinary export runs emit real timestamps
- public `generatedAt` means export time for the snapshot, not proof that an
  upstream repository changed at that exact moment

### 3. Ordinary local export

For a normal non-deterministic export:

```bash
cargo run -p dotrepo-cli -- public export --index-root index --out-dir public
```

You may also add `--stale-after-hours <hours>` for an advisory staleness window.
When deploying behind a subpath such as a project-site-style static host, add
`--base-path /<repo-name>` so public links resolve correctly from the hosted
root and point at the exported `index.json` / `profile.json` / `trust.json`
files. The current Cloudflare custom-domain deployment on `dotrepo.org` uses
`--base-path /`.

## Integrated gate and CI artifacts

Run the canonical review entrypoint on the integrated changes:

```bash
uv run python scripts/check_release_gate.py --output-root /tmp/dotrepo-release-gate
```

The gate builds from the real index, validates public contracts and quality,
packages the public tree and native install assets, smoke-tests extracted binaries
and the local same-origin runtime, then stages that export for Worker route smoke.
CI also checks VS Code lifecycle and desktop/mobile presentation. Root-path
Cloudflare and `/dotrepo` review-path exports are both exercised.

`--skip-release-bundle --skip-vsix` selects the lightweight public-only path.
`--skip-vsix` omits extension packaging only; report that omission and run full
packaging before declaring release completion. Index-only CI uses the lightweight
path; toolchain and `docs/` or `rfcs/` changes currently select the full gate through
[the scope classifier](../.github/workflows/ci.yml).

CI uploads the public tree/bundle and applicable install/VSIX artifacts. Full
release artifacts retain 14 days; lightweight public artifacts retain seven.
The separate operator gate uploads claim reports and the live seed-handoff public
tree. These are review evidence, not publication or independent-consumer proof.
Use [the release checklist](public-release-checklist.md) for publication evidence.

## Deployment and runtime

[Cloudflare setup](cloudflare-deploy.md) owns authentication, opt-in workflow
variables, restoration of deployed/archived history, publication serialization,
exact-source checks, and post-deploy smoke verification. Deploy the Worker and
its regenerated export together. A separate scheduled edge canary checks live
coherence; its artifacts establish actual run outcomes.

The static edge retains the current and previous immutable snapshots; historical
payloads belong in the configured archive. Private `query-input/` files serve
the runtime and are not restored from the public origin.

`dotrepo-public-query` serves local static files and dynamic routes from one
process. Hosted search reads the pointer plus the compact `repos/search.json`
export for both text and filtered matching, scanning that document in memory.
It does not fan out to every repository profile. A missing search document fails
rather than switching to unbounded reads. See [architecture](public-surface.md).

## Contract review

For identical source inputs and fixed review timestamps, layout, serialized
responses, links, validators, and snapshot files/hashes remain deterministic.
Ordinary exports intentionally vary freshness timestamps and resulting snapshot
identity. [Freshness definitions](public-freshness.md) distinguish source digest,
snapshot identity, export time, and factual record age.

Classify a change as source facts, response/selection/claim contract, or export-only
metadata before choosing expectations. The fixture pack pins exact outputs;
[wire compatibility](public-api-compatibility.md) catches key/link/error drift;
the integrated gate reviews current index output. Never change frozen source
captures to make a new parser pass.

## Related docs

- [`rfcs/0016-public-index-site-and-query-api.md`](../rfcs/0016-public-index-site-and-query-api.md)
- [`rfcs/0017-public-repository-summary-response.md`](../rfcs/0017-public-repository-summary-response.md)
- [`rfcs/0018-static-public-serving-and-freshness.md`](../rfcs/0018-static-public-serving-and-freshness.md)
- [`rfcs/0019-public-trust-and-query-wrappers.md`](../rfcs/0019-public-trust-and-query-wrappers.md)
- [`README.md`](../README.md)
