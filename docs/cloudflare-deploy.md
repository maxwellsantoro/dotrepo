# Cloudflare deploy setup

This doc covers how to configure the dotrepo Cloudflare Worker deployment.

Configure these three concerns independently:

- Worker runtime bindings for local `wrangler dev`
- local Cloudflare authentication for manual deploys
- GitHub Actions variables and secrets for the opt-in deploy workflow

## Files and paths

- Worker project: `cloudflare/hosted-query/`
- Worker config: `cloudflare/hosted-query/wrangler.jsonc`
- Local runtime vars example: `cloudflare/hosted-query/.dev.vars.example`
- Deploy workflow: `.github/workflows/public-cloudflare.yml`

## Local Worker runtime vars

For local `wrangler dev`, the runtime variables currently used are `BASE_PATH`
and `CANONICAL_HOST`.

The defaults in `wrangler.jsonc` are:

```jsonc
"vars": {
  "BASE_PATH": "/",
  "CANONICAL_HOST": "dotrepo.org"
}
```

If you want to override it locally:

1. Copy `cloudflare/hosted-query/.dev.vars.example` to
   `cloudflare/hosted-query/.dev.vars`
2. Edit `BASE_PATH` or `CANONICAL_HOST` if you need local overrides

Example:

```bash
cp cloudflare/hosted-query/.dev.vars.example cloudflare/hosted-query/.dev.vars
```

This is only for local Worker runtime bindings. It is not how GitHub deploy
auth is configured.

## Local Cloudflare auth

For local `wrangler deploy`, set Cloudflare auth in your shell:

```bash
export CLOUDFLARE_API_TOKEN=...
export CLOUDFLARE_ACCOUNT_ID=...
```

Then deploy from the Worker project:

```bash
cd cloudflare/hosted-query
npx wrangler deploy
```

If you prefer, `wrangler login` can also handle interactive local auth, but the
repo workflow is written around explicit env vars.

## GitHub Actions setup

The deploy workflow is opt-in. It only runs when the repo variable
`CLOUDFLARE_PUBLIC_DEPLOY_ENABLED` is set to `true`.

### Repository variables

Set these in GitHub repository settings under Variables:

- `CLOUDFLARE_PUBLIC_DEPLOY_ENABLED=true`
- `DOTREPO_PUBLIC_BASE_PATH=/`

`DOTREPO_PUBLIC_BASE_PATH` defaults to `/`; configured custom domains require `/`.
`DOTREPO_PUBLIC_STATE_BASE_URL` optionally selects the currently deployed HTTPS
origin used to restore snapshot history; it defaults to `https://dotrepo.org`.
Set it to the existing `workers.dev` origin when deploying a separate mirror.

### Repository secrets

Set these in GitHub repository settings under Secrets:

- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`

The workflow reads those values directly when it runs `wrangler deploy`.

## What the workflow does after deploy

The workflow runs after successful default-branch push CI, or through explicit
manual dispatch. The CI-triggered path checks out the tested commit. Index
automation explicitly dispatches it after its own checked fast-forward because
`GITHUB_TOKEN` pushes do not trigger downstream workflows. The exact-commit
landing sequence and failure recovery are documented in
[crawl automation](factual-crawl-automation.md#scheduled-enablement-and-landing).

The workflow serializes eligibility, build, and publication across trigger types.
It rejects an event whose commit no longer matches the default branch and rechecks
immediately before archive/deploy, so parallel agents must hand publication to
one coordinator rather than dispatch competing source revisions.

The workflow:

- restores the deployed snapshot log and current public payloads before building,
  including archive history when an R2 bucket is configured
- builds the validated export snapshot with that history already present
- stages that snapshot into `cloudflare/hosted-query/public-snapshot`
- runs Worker tests
- deploys the Worker with Wrangler
- captures the emitted deployed URL
- smoke-tests the live deployed Worker against the same validated export

PageDigest and snapshot restoration use the same bounded HTTP reader and explicit
`dotrepo-public-deploy/1.0` User-Agent. Transient transport failures and selected
HTTP failures receive bounded retries; persistent authorization/policy failures
stop immediately with a capped response diagnostic and Cloudflare request ID.
An HTTP 403 requires inspecting the reported policy error and edge configuration.
Restoration still validates source hashes, snapshot identity, and history before
changing local state; do not bypass it or seed an empty history to resume deploys.

The live smoke checks:

- the deployed `v0/meta.json`, `v0/files.json`, and `v0/repos/index.json`
  exactly match the reviewed export that was staged for deployment
- the deployed `v0/snapshots/log.json` and `v0/stats.json` exactly match the
  reviewed export and agree with the current pointer's file/repository counts
- `v0/meta.json` points at the digest-keyed tree under `v0/snapshots/`; direct
  snapshot responses are immutable while compatibility paths revalidate
- a deterministic sample of public paths from `v0/files.json`, including the
  core contract files and the first reviewed repository's exported JSON, matches
  the reviewed byte counts and SHA-256 hashes
- the homepage embedded snapshot state matches the deployed public JSON
- one emitted `queryTemplate` resolved with `repo.description`
- batch profile lookup, batch field lookup, search, compare, and relation
  traversal routes for the first reviewed repository

That keeps local review, pre-deploy smoke, and post-deploy smoke aligned on one
set of exported files and its snapshot ID.

## Snapshot retention and archive

The published retention contract is:

- current and previous immutable snapshots are kept in the Worker static asset
  bundle
- every published immutable snapshot is retrievable from the archive layer
- `/v0/snapshots/log.json` is append-only and never pruned

The Worker supports an optional `SNAPSHOT_ARCHIVE` R2 binding. When a direct
`/v0/snapshots/<snapshotId>/...` asset is not present in the static bundle, the
Worker attempts to read the same key from that binding before returning 404.
This keeps the hot path fast while avoiding the static-asset file-count ceiling
for historical snapshots.

Every deployment restores the live metadata, append-only log, and current
immutable file manifest into the clean runner. It checks public payload byte
counts and SHA-256 hashes before staging them as the next deployment's previous
snapshot. Private `query-input` files remain hidden and are not fetched from the
public origin. The exporter receives the restored log before computing stats,
so the reviewed export and deployed history remain identical. A missing or
inconsistent deployed state fails the deployment instead of resetting history.

For a manual deployment, run restoration before `public export`:

```bash
uv run python scripts/restore_cloudflare_public_state.py \
  --base-url https://dotrepo.org \
  --base-path / \
  --export-root release-gate/public \
  --staging-root cloudflare/hosted-query/public-snapshot
```

Initial deployment to an origin with no existing snapshot requires building and
staging its first export locally. Subsequent CI deployments restore that state.

Bucket creation and binding configuration are operator-owned setup steps:

```bash
npx wrangler r2 bucket create dotrepo-public-snapshot-archive
```

Then add the Worker binding in `cloudflare/hosted-query/wrangler.jsonc`:

```jsonc
"r2_buckets": [
  {
    "binding": "SNAPSHOT_ARCHIVE",
    "bucket_name": "dotrepo-public-snapshot-archive"
  }
]
```

Set GitHub variable `DOTREPO_PUBLIC_R2_ARCHIVE_BUCKET` to the bucket name to
enable the deploy workflow's archive upload step. The step runs:

```bash
uv run python scripts/archive_public_snapshot_r2.py \
  --public-root release-gate/public \
  --bucket "$DOTREPO_PUBLIC_R2_ARCHIVE_BUCKET"
```

Use `--dry-run` locally to inspect the `wrangler r2 object put` commands before
uploading. Real uploads first read and merge the existing archive log, reject
changes to published entries, and upload the log after all payloads succeed.
The deployment workflow also passes `--require-complete-history`, which aborts
publication if the reviewed export omitted archive entries. Standalone archive
uploads preserve remote history even when their local export starts empty.

Archive writes upload immutable snapshot objects under their public path keys,
for example:

```text
v0/snapshots/<snapshotId>/repos/index.json
v0/snapshots/<snapshotId>/files.json
v0/snapshots/log.json
```

The scheduled canary checks the pointer, canonical files, snapshot log, and
stats every run. After the archive binding is live and at least two snapshots
exist, set GitHub variable `DOTREPO_PUBLIC_ARCHIVE_CANARY_ENABLED=true` to make
the scheduled canary sample an older immutable snapshot URL. That prevents
archive rot from hiding behind a healthy current edge snapshot.

## Public origins

[`wrangler.jsonc`](../cloudflare/hosted-query/wrangler.jsonc) configures
`dotrepo.org` and `www.dotrepo.org` as custom domains, plus `workers.dev` serving.
The Worker permanently redirects `www` to `dotrepo.org` while preserving path
and query. Production links use `https://dotrepo.org/`.

Post-deploy smoke prefers a configured custom domain. If DNS/certificate
provisioning is incomplete, it can fall back to the emitted `workers.dev` URL.
Record which origin passed; a successful fallback is not proof that the custom
domain is healthy. Verify live state from the deploy/canary artifacts rather than
from this configuration alone.

## Recommended first run

1. Run the release gate locally:

```bash
uv run python scripts/check_release_gate.py --output-root /tmp/dotrepo-cloudflare-review --skip-vsix
```

2. Confirm the Worker dry-run passes locally.
3. Add the GitHub variables and secrets.
4. Trigger `.github/workflows/public-cloudflare.yml` manually.

## What not to use

- Do not put GitHub Actions secrets in `.dev.vars`.
- Do not rely on a root `.env` file for GitHub workflow deploy auth.
- Do not edit or commit generated `public/` or `release-gate/` trees; stage
  from a validated export snapshot instead.
- Do not treat the static asset bundle as the historical archive. It is the
  current+previous hot serving layer; R2 is the retention layer.
