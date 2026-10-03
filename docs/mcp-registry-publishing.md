# MCP registry publishing

dotrepo's MCP server is listed in the official MCP registry
(`registry.modelcontextprotocol.io`) as `io.github.maxwellsantoro/dotrepo`,
distributed as an MCPB bundle attached to GitHub releases. This is part of the
distribution workstream in [`ROADMAP.md`](../ROADMAP.md): the lookup surface
has to live where agent builders discover tools.

## How a release reaches the registry

Publishing is fully automated on version tags; no stored secrets are involved.

1. Pushing a `v*` tag runs `.github/workflows/release-artifacts.yml` as before:
   per-platform binary tarballs and the VSIX are built and attached to the
   GitHub release.
2. The `release` job additionally runs
   `scripts/package_mcpb_bundle.py`, which extracts the `dotrepo-mcp` binary
   from every platform tarball into one deterministic
   `dotrepo-mcp-<version>.mcpb` (an MCPB zip whose manifest selects the right
   binary per platform via `platform_overrides`), attaches it to the release,
   and rewrites `server.json` with the release-asset URL and the bundle's
   `fileSha256`.
3. The `mcp-registry` job then installs a **version-pinned** `mcp-publisher`
   binary (checksum-verified; see `MCP_PUBLISHER_VERSION` /
   `MCP_PUBLISHER_SHA256` in `.github/workflows/release-artifacts.yml` and
   `mcp-registry-publish.yml`), authenticates with `mcp-publisher login
   github-oidc` (GitHub Actions OIDC proves control of the
   `io.github.maxwellsantoro` namespace), and runs `mcp-publisher publish`
   against the updated `server.json`.

The checked-in [`server.json`](../server.json) is the template: its
`FILLED_AT_RELEASE` placeholders are intentionally invalid so a stale template
cannot be published by accident. The release pipeline fills them from the real
artifact before publishing.

## Version floor

The first publishable release is **v1.0.1 or later**. The v1.0.0 binaries
speak only `Content-Length`-framed JSON-RPC on stdio; the MCP specification's
stdio transport is newline-delimited JSON, so standard MCP clients cannot talk
to them. `dotrepo-mcp` now auto-detects both framings per message and responds
in kind (`read_jsonrpc_message_auto` in `dotrepo-transport`), and the CI smoke
test drives the spec-compliant newline framing. Do not point the registry at
the v1.0.0 assets.

## Manual fallback

The same flow can be run locally if the automated job is unavailable:

```bash
# Download the release tarballs for every platform
gh release download v<version> --pattern '*.tar.gz' --dir /tmp/rel

# Build the bundle and update server.json in place
uv run python scripts/package_mcpb_bundle.py \
  --tarball /tmp/rel/dotrepo-<version>-aarch64-apple-darwin.tar.gz \
  --tarball /tmp/rel/dotrepo-<version>-x86_64-unknown-linux-gnu.tar.gz \
  --version <version> \
  --output-dir /tmp/mcpb \
  --update-server-json server.json

# Attach the bundle to the release
gh release upload v<version> /tmp/mcpb/dotrepo-mcp-<version>.mcpb

# Publish the listing (interactive GitHub auth)
mcp-publisher login github
mcp-publisher publish
```

The bundle build is deterministic (fixed zip timestamps, sorted entries), so
rebuilding from the same tarballs always reproduces the same `fileSha256`.

## Verifying the listing

```bash
curl -s "https://registry.modelcontextprotocol.io/v0/servers?search=io.github.maxwellsantoro/dotrepo"
```

MCP clients validate `fileSha256` against the downloaded bundle before
installation; a hash mismatch means the release asset and the published
`server.json` are out of sync — republish from the actual asset.
