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

For local `wrangler dev`, the only runtime variable currently used is
`BASE_PATH`.

The Worker already defaults that in `wrangler.jsonc`:

```jsonc
"vars": {
  "BASE_PATH": "/dotrepo"
}
```

If you want to override it locally:

1. Copy `cloudflare/hosted-query/.dev.vars.example` to
   `cloudflare/hosted-query/.dev.vars`
2. Edit `BASE_PATH`

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
- `DOTREPO_PUBLIC_BASE_PATH=/dotrepo`

`DOTREPO_PUBLIC_BASE_PATH` is optional; the workflow defaults to `/dotrepo`.

### Repository secrets

Set these in GitHub repository settings under Secrets:

- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`

The workflow reads those values directly when it runs `wrangler deploy`.

## What the workflow does after deploy

The workflow in `.github/workflows/public-cloudflare.yml` now:

- builds the reviewed export snapshot
- stages that snapshot into `cloudflare/hosted-query/public-snapshot`
- runs Worker tests
- deploys the Worker with Wrangler
- captures the emitted deployed URL
- smoke-tests the live deployed Worker against the same reviewed export

The live smoke checks:

- `/<base>/v0/meta.json`
- one emitted `queryTemplate` resolved with `repo.description`

That keeps local review, pre-deploy smoke, and post-deploy smoke aligned on one
snapshot family.

## Current published shape

Right now the Worker config publishes to `workers.dev`.

That means the Cloudflare workflow can publish a live staging origin such as:

```text
https://dotrepo-public-hosted-query.<account-subdomain>.workers.dev/dotrepo/
```

This is useful for proving the Worker deployment path end to end, but it is not
the final public-origin cutover.

## Final cutover from Pages

To replace GitHub Pages as the primary public origin, configure a real
Cloudflare zone route or custom domain for this Worker and then update
`cloudflare/hosted-query/wrangler.jsonc` accordingly.

That cutover should happen only after:

1. the Worker deploy is stable on `workers.dev`
2. the deployed smoke checks keep passing in CI
3. the chosen public domain and base path are finalized
4. Pages is no longer treated as the canonical public origin in the docs

Until then, treat `workers.dev` as the live staging surface and GitHub Pages as
the primary documented public origin.

## Recommended first run

1. Run the release gate locally:

```bash
python3 scripts/check_release_gate.py --skip-vsix
```

2. Confirm the Worker dry-run passes locally.
3. Add the GitHub variables and secrets.
4. Trigger `.github/workflows/public-cloudflare.yml` manually.

## What not to use

- Do not put GitHub Actions secrets in `.dev.vars`.
- Do not rely on a root `.env` file for GitHub workflow deploy auth.
- Do not edit `public/` by hand before deploy; stage from a reviewed export
  snapshot instead.
