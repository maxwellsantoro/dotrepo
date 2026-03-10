# RFC 0007: LSP and VS Code scope

## Status
Draft

## Summary

dotrepo should provide a thin editor layer for the canonical manifest surface,
not a second product with its own semantics.

The first LSP and VS Code pass should focus on authoring and inspecting
`.repo` and overlay `record.toml` files by reusing existing core validation,
query, and trust behavior wherever possible.

The goal is to make the canonical record easier to read and repair in an
editor, while keeping the CLI and `dotrepo-core` as the semantic center of
gravity.

## Principles

- Reuse `dotrepo-core` for validation and trust-aware semantics.
- Prefer the canonical manifest surface over generated compatibility files.
- Surface canonical dot paths so editor help matches CLI and MCP behavior.
- Keep the VS Code extension thin: launch the server, wire commands, and avoid
  editor-only interpretation of the protocol.
- Do not let editor UX outrun the protocol or managed-sync contract.

## Supported files and roots

The first editor pass should support:

- native root `.repo` files
- overlay `record.toml` files

It should assume a single workspace root and the same manifest-resolution model
already used by the CLI:

- `.repo` when editing a native repository
- `record.toml` when editing an overlay record

The first pass should not provide semantic editing assistance for:

- `README.md`
- `SECURITY.md`
- `CONTRIBUTING.md`
- `CODEOWNERS`
- `evidence.md`

Those files remain normal text or Markdown editing surfaces unless and until a
later phase adds carefully scoped support.

## Supported workflows

The initial LSP experience should cover four workflows.

### 1. Validate the current manifest while editing

When a user opens or saves `.repo` or `record.toml`, the editor should surface
the same validation diagnostics that the CLI already produces.

This is the editor analogue of:

```bash
dotrepo validate
```

### 2. Understand what a field means

Hover should explain:

- the field name
- the canonical dot path
- the expected value shape
- any mode-aware constraint that matters at authoring time

Examples:

- `repo.build` is a string command
- `record.source` is required for overlays and invalid for native records
- `record.trust.provenance` is an ordered list of provenance terms

### 3. Discover available fields and enum values

Completion should help users add valid tables, keys, and common enum values
without making the editor responsible for semantic validation.

Examples:

- top-level tables such as `[record]`, `[repo]`, `[owners]`, `[docs]`, `[readme]`
- nested tables such as `[record.trust]` and `[compat.github]`
- enum values such as `mode = "native"` or `status = "canonical"`

### 4. Inspect trust-aware state from the editor shell

The first VS Code extension may expose thin commands that invoke existing CLI
flows such as:

- `dotrepo validate`
- `dotrepo trust`
- `dotrepo doctor`
- `dotrepo generate --check`

These commands should present existing output or structured results, not define
new precedence, sync, or trust behavior.

## Initial LSP feature set

### Diagnostics

Diagnostics are the core of the first release.

The server should:

- parse the current manifest text
- run the same validation rules as `dotrepo-core`
- return actionable diagnostics at open and save time
- keep severity aligned with the current core diagnostic model

Day-one diagnostics should cover:

- schema/version problems
- required-field violations
- mode-aware invalid combinations
- readme/custom-section path validation that already exists in core

The editor should not invent new lint classes that do not exist in the core
validation path.

### Hover

Hover should provide compact schema help with the canonical dot path.

Hover content should be driven by a small field catalog in the editor layer,
with semantics derived from the current v0.1 schema and RFCs. That catalog may
describe:

- field purpose
- expected type
- native-only or overlay-only constraints
- links to the relevant RFC or maintainer docs when useful

Hover should not evaluate repository state beyond what the current file already
contains.

### Completion

Completion should be schema-shaped rather than heuristic.

The initial server should support:

- table-name completion
- field-name completion
- enum-value completion for common controlled vocabularies
- short snippets for common skeletons such as `[record]`, `[repo]`, and
  `[record.trust]`

Completion items should expose the canonical dot path in detail text when
possible so authoring and query semantics stay visually aligned.

### Code actions

The first pass should not promise semantic code actions.

At most, the initial extension may expose editor commands that rerun existing
CLI flows. It should not attempt to autofix:

- authority conflicts
- managed-region marker layouts
- inferred import results
- missing trust metadata

If code actions arrive later, they should follow stable validation semantics
instead of preceding them.

## VS Code extension scope

The first VS Code extension should be a thin shell over the LSP server and the
existing CLI.

Its responsibilities are:

- activate on `.repo` and `record.toml`
- launch the dotrepo language server over stdio
- provide editor settings for the server or binary path if needed
- register a small set of commands that call existing CLI operations

It should avoid:

- custom truth models
- custom sync engines
- bespoke trust-resolution logic
- complex webviews for the first release

The extension should feel like a convenient entry point into the reference
toolchain, not a separate implementation.

## Core reuse boundary

The split between core and editor layers should stay explicit.

`dotrepo-core` should own:

- manifest parsing
- validation diagnostics
- query semantics and dot-path behavior
- trust and conflict reporting
- generate-check and doctor semantics

The LSP and extension layer may own:

- TOML position-to-field mapping
- schema help text and completion catalogs
- editor command wiring
- output presentation in the host editor

The editor layer should not reimplement:

- precedence rules
- trust vocabulary
- import heuristics
- managed-sync rules

## Non-goals for the first release

The first editor release should explicitly not try to solve:

- managed-region authoring or marker placement
- README or SECURITY.md semantic editing support
- `evidence.md` assistance
- index-wide repository search
- workspace or bundle authoring
- conflict resolution UI beyond surfacing existing trust output
- complex refactors or semantic autofix flows

Those are reasonable future topics, but they should not be bundled into the
first LSP pass.

## Follow-on issue mapping

- `#28`: implement manifest validation and diagnostics over LSP
- `#29`: add completion and hover for core schema fields
- `#30`: ship the first thin VS Code extension

The intended order is:

1. diagnostics
2. completion and hover
3. extension shell

That keeps the core semantic path ahead of the editor UX shell.
