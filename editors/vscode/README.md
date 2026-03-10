# dotrepo VS Code extension

This is the first thin VS Code shell for dotrepo.

It does three things:

- launches `dotrepo-lsp` for `.repo` and `record.toml`
- exposes validation diagnostics, hover help, and schema-shaped completion in the editor
- registers thin shell commands for `validate`, `trust`, `doctor`, and `generate --check`

It does **not** try to invent editor-only semantics. The extension is a shell
over the existing Rust binaries and follows the scope in
[`rfcs/0007-lsp-and-vscode-scope.md`](../../rfcs/0007-lsp-and-vscode-scope.md).

## First release features

- diagnostics for invalid `.repo` and `record.toml` files
- hover help for core schema fields and trust vocabulary
- completion for section headers, core keys, and common enum values
- command palette entries for:
  - `dotrepo: Validate Current Manifest`
  - `dotrepo: Trust Current Manifest`
  - `dotrepo: Doctor Current Root`
  - `dotrepo: Generate Check Current Root`

## Non-goals

The first release does **not** provide:

- managed-region marker authoring
- README, `SECURITY.md`, `CODEOWNERS`, or `evidence.md` semantic editing
- authority-conflict resolution UI
- semantic autofix or code actions
- bundle/workspace authoring support

## Install for local use

The extension expects `dotrepo-lsp` and `dotrepo` to be available on `PATH` by
default.

One workable local path is:

```bash
cargo build -p dotrepo-lsp -p dotrepo-cli
export PATH="/path/to/dotrepo/target/debug:$PATH"
```

Then, in this `editors/vscode/` directory:

```bash
npm install
```

Open the `editors/vscode/` folder in VS Code and run the extension in an
Extension Development Host.

## Settings

If the binaries are not on `PATH`, configure:

- `dotrepo.languageServer.command`
- `dotrepo.languageServer.args`
- `dotrepo.cli.command`
- `dotrepo.cli.args`

For local development inside the dotrepo workspace, a cargo-based override is:

```json
{
  "dotrepo.languageServer.command": "cargo",
  "dotrepo.languageServer.args": ["run", "-p", "dotrepo-lsp", "--"],
  "dotrepo.cli.command": "cargo",
  "dotrepo.cli.args": ["run", "-p", "dotrepo-cli", "--"]
}
```

That override is mainly for working on dotrepo itself. For normal use on other
repositories, prefer installed binaries or absolute paths.

## Root resolution

The shell commands use:

- the directory containing the active `.repo`, or
- the directory containing the active `record.toml`

If no manifest is active, the extension falls back to the first workspace
folder.
