# Install

For a stable installation, use the
[`v1.0.3` release](https://github.com/maxwellsantoro/dotrepo/releases/tag/v1.0.3).
It provides `dotrepo`, `dotrepo-public-query`, `dotrepo-lsp`, and `dotrepo-mcp`.
The current `main` source is the unreleased `2.0.0-alpha.0` development line.

Read [release compatibility](release-compatibility.md) for the bounded stable
safety update and remaining development-only contracts. Stable rejects
`promotion-report --apply`, preserves Make/Just entrypoints, withholds ambiguous
or non-running commands, and caps MCP response bodies. Import reads require
bounded regular files without symlink traversal, forced imports refuse
symlink/shared-hardlink overwrites, and dynamic Rake sources are withheld.
Retained per-field assessments, execution contexts, and newer MCP target checks
remain unreleased.

## Download a stable bundle

Choose the asset for your platform from the
[release page](https://github.com/maxwellsantoro/dotrepo/releases/tag/v1.0.3),
verify it against its matching `.sha256` file, extract it, and put the binaries
from `bin/` on your `PATH`.

Bundle names include the version and target, for example:

- `dotrepo-1.0.3-x86_64-unknown-linux-gnu.tar.gz`
- `dotrepo-1.0.3-aarch64-apple-darwin.tar.gz`

Use an asset that is actually listed for your platform; the source build below
is the alternative when no matching prebuilt bundle is available.

## Install from crates.io

With a Rust toolchain, pin the stable packages explicitly:

```bash
cargo install dotrepo-cli --version 1.0.3 --locked
cargo install dotrepo-mcp --version 1.0.3 --locked
cargo install dotrepo-lsp --version 1.0.3 --locked
```

Install only the tools you need. `dotrepo-cli` supplies both the `dotrepo` and
`dotrepo-public-query` executables. The separate `dotrepo` alias package in the
development source tree is absent from the stable release; use the package
names above for stable installs. Do not install both CLI packages, since they
provide the same `dotrepo` executable.

Avoid unpinned install examples when reproducibility matters. A package's latest
README can describe a different source version from the binary you installed.

## Build from source

For a reproducible stable source build, use a separate checkout of the release
tag:

```bash
git clone --branch v1.0.3 --depth 1 https://github.com/maxwellsantoro/dotrepo.git dotrepo-1.0.3
cd dotrepo-1.0.3
cargo build --locked --release -p dotrepo-cli --bins -p dotrepo-lsp -p dotrepo-mcp
export PATH="$PWD/target/release:$PATH"
```

For contributor builds in an existing checkout:

```bash
cargo build --locked -p dotrepo-cli --bins -p dotrepo-lsp -p dotrepo-mcp
export PATH="$PWD/target/debug:$PATH"
```

Building `main` opts into unreleased behavior and breaking Rust API changes,
including `FieldConfidence::Suspect`. Passing `--release` changes optimization;
it does not turn development source into a published stable release.

## Maintainer CI

`dotrepo ci init --version 1.0.3` creates a GitHub Actions workflow that downloads
one pinned release bundle and runs `validate`, `query`, `trust`, `doctor`, and
`generate --check`. It targets `ubuntu-latest` and the
`x86_64-unknown-linux-gnu` bundle.

Pass the version explicitly for a reproducible workflow. Stable `v1.0.3` retains
the `1.0.1` default frozen before publication; use `--version 1.0.3` to select the
safety release. Development `main` now pins `1.0.3`. Neither discovers the latest
release at runtime.

## MCP clients

After installing `dotrepo-mcp`, configure it as a stdio server. See the
[consumer integration guide](external-consumer-integration.md) for a configuration
example and lookup arguments, and [MCP network policy](release-compatibility.md#mcp-network-policy)
for default origins and opt-in overrides.

## VS Code extension

Install the `.vsix` listed with the matching GitHub release using
`Extensions: Install from VSIX...`. The extension expects `dotrepo` and
`dotrepo-lsp` on `PATH` by default, so install those binaries too.

See the
[stable extension guide](https://github.com/maxwellsantoro/dotrepo/blob/v1.0.3/editors/vscode/README.md)
for that release's settings, or the [development guide](../editors/vscode/README.md)
when loading the extension from this checkout.
