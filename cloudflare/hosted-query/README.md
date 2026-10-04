# Cloudflare hosted query Worker

This Worker serves the dotrepo hosted public surface from one reviewed export
snapshot:

- static files from `public-snapshot/`
- live `v0` query responses reconstructed from `query-input/*.json`
- live `v0` batch profile and batch query responses from the same staged
  snapshot
- live hosted profile search, factual profile compare, and typed
  relation traversal from the same staged snapshot

## Local workflow

For a Worker-only change, run `npm ci` and `npm test` in this directory first.
Use the lightweight public gate to review export integration; the coordinator
runs complete packaging on the integrated change as required by
[CONTRIBUTING](../../CONTRIBUTING.md#local-checks). Concurrent agents use separate
export/staging roots; only the deployment owner writes the shared staged snapshot.

1. Generate or refresh a public export.
2. Stage that export into `public-snapshot/`.
3. Run tests or `wrangler dev`.

Typical commands from the repo root:

```bash
uv run python scripts/check_release_gate.py --output-root /tmp/dotrepo-worker-review --skip-release-bundle --skip-vsix

uv run python scripts/sync_cloudflare_public_snapshot.py \
  --input /tmp/dotrepo-worker-review/public \
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

CI restores the deployed append-only history and current public snapshot before
exporting, then stages that snapshot alongside the new export. Public payloads
are verified against the immutable file manifest during restoration.

GitHub repository routes accept owner, repository, and host casing variations.
When a spelling misses, the Worker resolves it against the inventory for the
same immutable snapshot and returns its canonical identity. The inventory is
cached by snapshot for batch requests. Other hosts retain exact case matching.
