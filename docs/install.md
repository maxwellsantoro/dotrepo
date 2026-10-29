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

## Preferred install path

Download the latest matching release bundle for your platform from the GitHub
release assets for the current tag, then extract it and put the binaries from
`bin/` on your `PATH`.

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

## Qualify a stable maintenance release

The 1.0.4 maintenance candidate backports main's root-aware output writer while
retaining stable CLI arguments, MCP tool schemas, and ordinary output formats.
Use `scripts/compare_stable_outputs.py` with independently installed binary
folders to compare ordinary generate/check, native and overlay import/force,
validation, query, trust, doctor, MCP negotiation, tool schemas, and MCP import.
The comparison uses ordinary files only and reports its explicit temporary-path,
patch-version, and timestamp normalizations alongside both sets of outputs.

```bash
uv run python scripts/compare_stable_outputs.py \
  --baseline-bin /tmp/dotrepo-1.0.3/bin \
  --candidate-bin /tmp/dotrepo-1.0.4/bin \
  --output /tmp/dotrepo-1.0.4-ordinary.json
```

Run the existing native refusal regressions against the fixed source candidate:

```bash
cargo test --locked -p dotrepo-core --lib output::tests -- --nocapture
cargo test --locked -p dotrepo-cli --test write_safety_contract -- --nocapture
```

For a packaged or freshly installed fixed candidate, point the same CLI suite at
its binary with `DOTREPO_TEST_CLI_BIN=/absolute/path/to/dotrepo`. Do not run that
suite against an older unfixed binary; older public releases are ordinary-output
comparison baselines only. CI requires the native Linux and Windows suites via
`ci-gate`. Cross-compilation alone does not establish native Windows behavior.

The full release gate includes binary and VSIX packaging. Before publication,
validate all six public crates together with
`cargo publish --dry-run --locked --workspace --exclude dotrepo-crawler`; this
checks their unpublished interdependencies as one candidate. After tag
publication, `verify-public-installs` downloads and checksums public bundles on
Linux and macOS, installs exact CLI/MCP/LSP versions from crates.io into a fresh
prefix, compares ordinary bundle/registry outputs, and runs the existing CLI
refusal suite against both fixed installs. Release build success alone does not
establish that these fresh public installs pass.
