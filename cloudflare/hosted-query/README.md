# Cloudflare hosted query Worker

This Worker serves the dotrepo hosted public surface from one reviewed export
snapshot:

- static files from `public-snapshot/`
- live `v0` query responses reconstructed from `query-input/*.json`

## Local workflow

1. Generate or refresh a public export.
2. Stage that export into `public-snapshot/`.
3. Run tests or `wrangler dev`.

Typical commands from the repo root:

```bash
python3 scripts/check_release_gate.py --skip-vsix

python3 scripts/sync_cloudflare_public_snapshot.py \
  --input release-gate/public \
  --output cloudflare/hosted-query/public-snapshot

cd cloudflare/hosted-query
npm ci
npm test
npx wrangler dev
```

If you want to override the local Worker base path, copy
`cloudflare/hosted-query/.dev.vars.example` to `.dev.vars` and edit `BASE_PATH`.
For Cloudflare auth and GitHub Actions setup, see
[`docs/cloudflare-deploy.md`](../../docs/cloudflare-deploy.md).

## Deployment

The Worker expects the staged `public-snapshot/` tree to come from the same
reviewed export snapshot that release review inspected.
