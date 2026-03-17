# Install

dotrepo now has a release-artifact path for the core toolchain binaries. The
intended install surface is:

- `dotrepo`
- `dotrepo-lsp`
- `dotrepo-mcp`

These are built and packaged by `.github/workflows/release-artifacts.yml`.

## Preferred install path

Download the latest matching release bundle for your platform from the GitHub
release assets for the current tag, then extract it and put the binaries from
`bin/` on your `PATH`.

The current bundles are named like:

- `dotrepo-1.0.0-x86_64-unknown-linux-gnu.tar.gz`
- `dotrepo-1.0.0-aarch64-apple-darwin.tar.gz`

Each bundle also includes a matching `.sha256` file.

The same workflow also publishes a VS Code extension package named like:

- `dotrepo-vscode-v1.0.0.vsix`

Install that in VS Code with `Extensions: Install from VSIX...` if you want the
thin editor shell without loading the workspace extension directly.

## Build from source

If you are developing dotrepo itself or want a local debug build:

```bash
cargo build -p dotrepo-cli -p dotrepo-lsp -p dotrepo-mcp
export PATH="/path/to/dotrepo/target/debug:$PATH"
```

For release-style local binaries:

```bash
cargo build --release -p dotrepo-cli -p dotrepo-lsp -p dotrepo-mcp
export PATH="/path/to/dotrepo/target/release:$PATH"
```

## VS Code shell

The VS Code extension remains thin. It expects `dotrepo` and `dotrepo-lsp` on
`PATH` by default, so the release-artifact bundles are the preferred runtime
dependency even when the extension itself is still loaded from the workspace.

See [`editors/vscode/README.md`](../editors/vscode/README.md) for the extension
shell details and settings overrides.
