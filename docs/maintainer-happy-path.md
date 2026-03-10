# Maintainer happy path

This is the canonical v0.1 maintainer flow for a repository that wants an
in-repo `.repo` file as its source of truth.

Use [`examples/native-minimal/`](../examples/native-minimal/) as the reference
repository while reading this guide. It already contains:
- a canonical root [`.repo`](../examples/native-minimal/.repo)
- generated conventional surfaces such as [`README.md`](../examples/native-minimal/README.md)
- a starter CI workflow at [`.github/workflows/dotrepo-check.yml`](../examples/native-minimal/.github/workflows/dotrepo-check.yml)

## Start the record

Choose one bootstrap path:
- `cargo run -p dotrepo-cli -- --root <repo> init` if you want to author a canonical `.repo` from scratch.
- `cargo run -p dotrepo-cli -- --root <repo> import` if you want to bootstrap from existing `README.md`, `CODEOWNERS`, and `SECURITY.md` content first.

After that first step, treat the root `.repo` as the source of truth and keep
generated compatibility surfaces in sync from it.

## Canonical local loop

Run the same loop the example repo uses:

```bash
cargo run -p dotrepo-cli -- --root examples/native-minimal validate
cargo run -p dotrepo-cli -- --root examples/native-minimal query repo.build --raw
cargo run -p dotrepo-cli -- --root examples/native-minimal trust
cargo run -p dotrepo-cli -- --root examples/native-minimal doctor
cargo run -p dotrepo-cli -- --root examples/native-minimal generate --check
```

What each command answers:
- `validate` confirms that the current `.repo` is structurally valid.
- `query` gives scripts and tools a stable way to read specific fields from the manifest.
- `trust` is the human-facing inspection surface for status, provenance, authority handoff, and competing records.
- `doctor` reports whether supported conventional surfaces are `fully_generated`, `partially_managed`, `unmanaged`, `malformed_managed`, or in an unsupported state.
- `generate --check` fails on drift inside fully generated or partially managed surfaces, but does not fail solely because an unmanaged file exists.

## Inspect authority handoff and conflicts

Use `trust` when you need to understand why one record won:

```bash
cargo run -p dotrepo-cli -- --root <repo-or-index-scope> trust
cargo run -p dotrepo-cli -- --root <repo-or-index-scope> trust --json
```

The human-facing output should tell you:
- which record was selected
- why it won
- which competing records remain visible
- whether those competing records are `superseded` or `parallel`
- the source, confidence, provenance, and notes attached to each record

Use `trust --json` when MCP clients, scripts, or tests need the same
conflict-aware structure returned by `dotrepo-core`.

If you need one field together with the same selection context, use:

```bash
cargo run -p dotrepo-cli -- --root <repo-or-index-scope> query repo.build --json
```

`query --raw` remains available for single-record scalar lookups, but it now
refuses when competing records exist so scripts do not silently discard trust
context.

## Source-of-truth rule

For the example repo, the root `.repo` is authoritative. Generated files such as
`README.md`, `.github/CODEOWNERS`, `.github/SECURITY.md`, `CONTRIBUTING.md`, and
the pull request template are compatibility surfaces, not the primary editing
surface. If `generate --check` fails, update the generated files from `.repo`
rather than patching them by hand.

`doctor` is the guardrail before enabling more generated surfaces in an existing
repository. It now distinguishes:
- `fully_generated`: the whole file is dotrepo-owned
- `partially_managed`: only the marked region is dotrepo-owned
- `unmanaged`: the file exists outside dotrepo management
- `malformed_managed`: markers are broken and must be fixed

That makes it possible to adopt managed regions incrementally without treating
every existing Markdown file as drift.

## CI

The example workflow runs the same maintainer path in CI:

```bash
cargo run -p dotrepo-cli -- --root examples/native-minimal validate
cargo run -p dotrepo-cli -- --root examples/native-minimal query repo.build --raw
cargo run -p dotrepo-cli -- --root examples/native-minimal trust
cargo run -p dotrepo-cli -- --root examples/native-minimal doctor
cargo run -p dotrepo-cli -- --root examples/native-minimal generate --check
```

That is the intended v0.1 contract for a native repo:
- validate the canonical record
- make one or more machine-facing queries succeed
- surface trust metadata and any authority conflicts explicitly
- inspect conventional surface states explicitly
- fail the build if fully generated or partially managed surfaces drift
