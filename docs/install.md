# Install

dotrepo now has a release-artifact path for the core toolchain binaries. The
intended install surface is:

- `dotrepo`
- `dotrepo-public-query`
- `dotrepo-lsp`
- `dotrepo-mcp`

These are built and packaged by `.github/workflows/release-artifacts.yml`.

For native repos that want the canonical maintainer CI loop, `dotrepo ci init`
scaffolds a GitHub Actions workflow that downloads one pinned release bundle
and runs `validate`, `query`, `trust`, `doctor`, and `generate --check`.
The current scaffold target is `ubuntu-latest` with the
`x86_64-unknown-linux-gnu` release bundle.
The default pin is the latest published stable release, not the version of a
development build used to generate the file. Pass `--version <release>` to pin
a different published release explicitly.

## Preferred install path

Download the latest matching **stable** release bundle for your platform from
the GitHub release assets (currently the `v1.0.x` line, for example `v1.0.1`),
then extract it and put the binaries from `bin/` on your `PATH`.

### Stable vs development line

| Line | Where | Who should use it |
|------|--------|-------------------|
| **Stable `1.0.x`** | Latest non-prerelease GitHub release and crates.io versions `1.0.x` | End users, CI pins, MCP clients in production |
| **Development `2.0.0-alpha.x`** | `main` and prerelease tags only | Contributors and early adopters accepting public Rust API changes (for example `FieldConfidence::Suspect`) |

Do not install crates.io `2.0.0-alpha.0` (or build `main`) into production agent
toolchains unless you intend to track breaking API changes. The default
`dotrepo ci init` scaffold pins the latest **stable** published release, not
the version of a local development binary used to generate the workflow.

## Install from crates.io

The toolchain crates are published to crates.io, so a Rust toolchain is the
only prerequisite:

```bash
cargo install dotrepo        # installs `dotrepo` (prefer latest 1.0.x for production)
cargo install dotrepo-mcp    # installs `dotrepo-mcp`
cargo install dotrepo-lsp    # installs `dotrepo-lsp`
```

Pin explicitly when you need reproducibility:

```bash
cargo install dotrepo --version 1.0.1
```

`dotrepo` is a thin alias for `dotrepo-cli`; install `dotrepo-cli` instead if
you also want the `dotrepo-public-query` binary. Install one or the other, not
both — they provide the same `dotrepo` binary.

Published crate versions track tagged releases: the crates.io source for a
version matches the GitHub release tag of the same version, not the tip of
`main`.

Release bundles are named like:

- `dotrepo-<version>-x86_64-unknown-linux-gnu.tar.gz`
- `dotrepo-<version>-aarch64-apple-darwin.tar.gz`

Each bundle also includes a matching `.sha256` file.

The same workflow also publishes a VS Code extension package named like:

- `dotrepo-vscode-v1.0.0.vsix`

Install that in VS Code with `Extensions: Install from VSIX...` if you want the
thin editor shell without loading the workspace extension directly.

## Build from source

If you are developing dotrepo itself or want a local debug build:

```bash
cargo build -p dotrepo-cli --bins -p dotrepo-lsp -p dotrepo-mcp
export PATH="/path/to/dotrepo/target/debug:$PATH"
```

For release-style local binaries:

```bash
cargo build --release -p dotrepo-cli --bins -p dotrepo-lsp -p dotrepo-mcp
export PATH="/path/to/dotrepo/target/release:$PATH"
```

## VS Code shell

The VS Code extension remains thin. It expects `dotrepo` and `dotrepo-lsp` on
`PATH` by default, so the release-artifact bundles are the preferred runtime
dependency even when the extension itself is still loaded from the workspace.

See [`editors/vscode/README.md`](../editors/vscode/README.md) for the extension
shell details and settings overrides.
