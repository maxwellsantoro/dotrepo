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
