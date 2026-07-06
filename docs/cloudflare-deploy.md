# Cloudflare deploy setup

This doc covers how to configure the dotrepo Cloudflare Worker deployment.

It separates three concerns:

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

The Worker already defaults that in `wrangler.jsonc`:

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

`DOTREPO_PUBLIC_BASE_PATH` is optional; the workflow now defaults to `/`.

### Repository secrets

Set these in GitHub repository settings under Secrets:

- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`

The workflow reads those values directly when it runs `wrangler deploy`.

## What the workflow does after deploy

The workflow in `.github/workflows/public-cloudflare.yml` now:

- builds the validated export snapshot
- stages that snapshot into `cloudflare/hosted-query/public-snapshot`
- runs Worker tests
- deploys the Worker with Wrangler
- captures the emitted deployed URL
- smoke-tests the live deployed Worker against the same validated export

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
- `/<base>/v0/meta.json`
- one emitted `queryTemplate` resolved with `repo.description`
- batch profile lookup, batch field lookup, search, compare, and relation
  traversal routes for the first reviewed repository

That keeps local review, pre-deploy smoke, and post-deploy smoke aligned on one
snapshot family.

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

Use `--dry-run` locally to inspect the exact `wrangler r2 object put` commands
before uploading.

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

## Published shape

The Worker config publishes to `workers.dev`.

It also now declares `dotrepo.org` as the production custom domain in
`cloudflare/hosted-query/wrangler.jsonc`.

The Worker also declares `www.dotrepo.org` and redirects it permanently to
`dotrepo.org`, preserving path and query string. That keeps one canonical host
for the future homepage and the hosted public API.

That means the Cloudflare workflow can publish to:

```text
https://dotrepo.org/
```

and continue to keep a `workers.dev` staging origin such as:

```text
https://dotrepo-public-hosted-query.<account-subdomain>.workers.dev/
```

The workflow now prefers the custom domain for the post-deploy smoke check when
one is declared in the Wrangler config. If the custom domain does not resolve
yet from CI, the workflow falls back to the deployed `workers.dev` URL until
Cloudflare DNS and certificate provisioning complete.

## Production shape

The production public origin is now `https://dotrepo.org/`.

`workers.dev` remains useful as a staging origin and as a fallback smoke target
while custom-domain DNS or certificate provisioning catches up during deploys,
but it is not the canonical public host.

## Recommended first run

1. Run the release gate locally:

```bash
uv run python scripts/check_release_gate.py --skip-vsix
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
