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
- `trust` surfaces status, provenance, confidence, and source context in one place.
- `doctor` tells you whether conventional surfaces exist outside dotrepo management.
- `generate --check` fails when generated files have drifted from the canonical `.repo`.

## Source-of-truth rule

For the example repo, the root `.repo` is authoritative. Generated files such as
`README.md`, `.github/CODEOWNERS`, `.github/SECURITY.md`, `CONTRIBUTING.md`, and
the pull request template are compatibility surfaces, not the primary editing
surface. If `generate --check` fails, update the generated files from `.repo`
rather than patching them by hand.

`doctor` is the guardrail before enabling more generated surfaces in an existing
repository. It tells you whether you still have unmanaged conventional files
that should be imported, normalized, or left alone deliberately.

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
- surface trust metadata explicitly
- confirm there are no unmanaged conventional files
- fail the build if generated surfaces drift
