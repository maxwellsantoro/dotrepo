# Maintainer happy path

This is the canonical v0.1 maintainer flow for a repository that wants an
in-repo `.repo` file as its source of truth.

This guide assumes `dotrepo` is installed and on your `PATH`.
If you are working inside the dotrepo workspace itself, replace `dotrepo` with
`cargo run -p dotrepo-cli --`.

Use [`examples/native-minimal/`](../examples/native-minimal/) as the reference
repository while reading this guide. It already contains:
- a canonical root [`.repo`](../examples/native-minimal/.repo)
- generated conventional surfaces such as [`README.md`](../examples/native-minimal/README.md)
- a starter CI workflow at [`.github/workflows/dotrepo-check.yml`](../examples/native-minimal/.github/workflows/dotrepo-check.yml)

## Start the record

Choose one bootstrap path:
- `dotrepo --root <repo> init` if you want to author a canonical `.repo` from scratch.
- `dotrepo --root <repo> import` if you want to bootstrap from existing `README.md`, `CODEOWNERS`, and `SECURITY.md` content first.

After that first step, treat the root `.repo` as the source of truth and keep
generated compatibility surfaces in sync from it.

To scaffold the native-repo CI check loop, run:

```bash
dotrepo --root <repo> ci init
```

That writes `.github/workflows/dotrepo-check.yml` with the same release-binary
workflow shape used by the native example repo. Pass `--version <x.y.z>` when
you want to pin a different dotrepo release than the current CLI version, or
`--force` to overwrite an existing workflow file.

Current scope and constraints:
- `ci init` is supported only for native records with a valid root `.repo`.
- the scaffold currently targets GitHub Actions on `ubuntu-latest`
- it installs the `x86_64-unknown-linux-gnu` release bundle and runs `dotrepo`
  from `PATH`

Native import now chooses `compat.github.*` conservatively from on-disk files:
- it enables `generate` only when the checked-in surface already matches the
  current dotrepo renderer closely enough that full ownership is honest
- richer handwritten surfaces stay `skip` until you inspect them with `doctor`
  and `preview`, then adopt them explicitly if needed

Do not assume every conventional community file should immediately be marked
`generate`.

- `generate` is honest only when dotrepo can reproduce the full file from the
  current manifest and renderer.
- For rich handwritten `README.md`, `SECURITY.md`, or `CONTRIBUTING.md` files,
  prefer managed regions when you want dotrepo to own one canonical block while
  preserving surrounding prose.
- For `CODEOWNERS` and pull request templates, partial management is not
  supported today. Use `generate` only if the current dotrepo template is the
  file you actually want; otherwise leave the file unmanaged.

## Canonical local loop

Run the same loop the example repo uses locally:

```bash
dotrepo --root examples/native-minimal validate
dotrepo --root examples/native-minimal query repo.build --raw
dotrepo --root examples/native-minimal trust
dotrepo --root examples/native-minimal doctor
dotrepo --root examples/native-minimal generate --check
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
dotrepo --root <repo-or-index-scope> trust
dotrepo --root <repo-or-index-scope> trust --json
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
dotrepo --root <repo-or-index-scope> query repo.build --json
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

Use `doctor` before switching a surface to `generate` in an existing repo. The
important maintainer question is not just "is this file valid?" but "can
dotrepo truthfully reproduce the file we want from `.repo`?" If the answer is
"only a narrow stub," prefer managed regions for supported Markdown files or
leave the file unmanaged.

For supported Markdown surfaces, the incremental adoption loop is now explicit:

```bash
dotrepo --root <repo> doctor --json
dotrepo --root <repo> preview --surface contributing --json
dotrepo --root <repo> manage contributing --adopt
dotrepo --root <repo> generate --check
```

- `preview --surface ...` shows the current file, the proposed managed result,
  whether unmanaged prose would be dropped, and which ownership mode is
  recommended.
- `doctor --json` and `preview --json` are also the semi-stable machine-facing
  adoption reports for scripts, editors, and MCP clients. The field-level
  contract is documented in [`sync-boundaries.md`](./sync-boundaries.md).
- `manage <surface> --adopt` is the explicit conversion path for
  `README.md`, `SECURITY.md`, and `CONTRIBUTING.md`. It preserves the current
  prose and inserts one canonical managed region instead of guessing through
  malformed or unsupported layouts.
- For `SECURITY.md` and `CONTRIBUTING.md`, set `compat.github.<surface> =
  "generate"` before adoption so the managed block participates in the normal
  generate / generate-check loop.

For the concrete boundary between supported sync, unmanaged files, malformed
markers, and unsupported layouts, see
[`sync-boundaries.md`](./sync-boundaries.md).

## CI

The example workflow and `dotrepo ci init` use the same command contract in CI.
The checked-in example file also includes the release-binary install step:

```bash
dotrepo --root . validate
dotrepo --root . query repo.build --raw
dotrepo --root . trust
dotrepo --root . doctor
dotrepo --root . generate --check
```

That is the intended v0.1 contract for a native repo:
- validate the canonical record
- make one or more machine-facing queries succeed
- surface trust metadata and any authority conflicts explicitly
- inspect conventional surface states explicitly
- fail the build if fully generated or partially managed surfaces drift
