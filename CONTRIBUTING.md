# Contributing to dotrepo

dotrepo is a protocol, a reference Rust toolchain, and a public repository
index.
Contributions are welcome across all three, but the standard is reviewable,
tested changes rather than speculative surface area.

## Where to contribute

- Protocol and schema: changes to `.repo`, trust semantics, claim flow, or the
  public JSON contracts.
- Toolchain: CLI, MCP, LSP, import, validation, generate-check, docs, and
  release workflow improvements.
- Public index: evidence-backed overlay records, claim context, and automation
  under `index/` and `scripts/`.

## Path containment limits

User-facing CLI writes and MCP imports use the shared root-aware output writer.
The explicitly selected root may be an alias; descendant symlinks/reparse points,
nonregular files, and shared-hardlink outputs are refused. Unix traverses and
creates descendants relative to pinned directory descriptors with no-follow
opens. Windows retains ancestor handles without delete sharing and rejects
reparse points. Every destination is opened without truncation and checked
before existing files change. Existing inodes, ownership, permissions, and ACLs
are preserved, including write-only files and traverse-only directories.

Use `write_repository_outputs` or `RepositoryWriter` for repository-derived
destinations; the legacy `write_import_outputs` API has caller-selected paths and
does not establish containment beneath a separately selected repository root.
Reads elsewhere may still use canonicalization with time-of-check/time-of-use
limits. Neither read nor write containment is a filesystem sandbox against an
active same-user actor moving already-open directories or adding a hardlink
after the final metadata check. Batch preflight prevents partial writes on unsafe
destinations; later I/O failures are not a multi-file transaction.

Import text inputs use a stricter contract: regular files only, no symlinks
(including contained links), and at most 2 MiB per input. Conventional files,
workflows, relation discovery and deterministic deepening share this reader.
Unix opens each descendant relative to a pinned directory with `O_NOFOLLOW`.
Windows refuses reparse paths and opens the leaf without following it; concurrent
ancestor replacement remains a best-effort limit. The caller controls the root
and its ancestors, so this does not isolate an importer from an actor who can
move the selected root itself.

Forced import refuses existing output symlinks, nonregular files and shared
hardlinks before truncation. This preserves the public import interface; it
does not grant permission to overwrite unrelated repository metadata.

## Before you open a PR

- Read the shortest relevant doc first instead of starting from the full RFC
  set. Use [`README.md`](README.md) for the main entry points and
  [`docs/README.md`](docs/README.md) for the documentation map.
- Use [`ROADMAP.md`](ROADMAP.md) for product direction, active execution, and
  milestone gates.
- If you are changing the protocol shape or a public contract, update the
  corresponding RFC or contract doc in the same patch.
- Keep trust, provenance, and conflict surfacing explicit. dotrepo should not
  silently flatten competing records or overstate confidence.

## Local checks

Create the locked Python environment before running repository tooling. All
Python commands in this repository must go through `uv run`.

```bash
uv venv
uv sync --dev --locked
uv run pytest
```

Run the core workspace checks:

```bash
cargo fmt --all -- --check
cargo clippy --workspace --all-targets -- -D clippy::correctness -W clippy::perf
cargo test --workspace
```

If you touched the maintainer flow or generated surfaces, also run:

```bash
cargo run -p dotrepo-cli -- --root examples/native-minimal validate
cargo run -p dotrepo-cli -- --root examples/native-minimal query repo.build --raw
cargo run -p dotrepo-cli -- --root examples/native-minimal trust
cargo run -p dotrepo-cli -- --root examples/native-minimal doctor
cargo run -p dotrepo-cli -- --root examples/native-minimal generate --check
```

If you touched the public index, claims, or evidence rules, also run:

```bash
cargo run -p dotrepo-cli -- validate-index --index-root index
uv run python scripts/check_operator_claim_gate.py --output-root /tmp/dotrepo-operator-gate
```

If you touched public export, release packaging, or the hosted public surface,
also run:

```bash
uv run python scripts/check_release_gate.py --output-root /tmp/dotrepo-release-gate --skip-vsix
```

## Public index contributions

The normal growth path is autonomous: deterministic extraction and validation
resolve what they can, constrained model tiers adjudicate only unresolved
fields, and machine gates decide whether a generated overlay can publish.
Generated records do not wait for routine human approval.

Manual overlay contributions are also welcome. They use the same evidence and
trust contracts, with pull-request review as an additional contribution gate.

Overlay submissions live under:

```text
index/repos/<host>/<owner>/<repo>/
  record.toml
  evidence.md
```

Use these repo-local docs together:

- [`index/README.md`](index/README.md) for the index layout and evidence rubric
- [`index/evidence-template.md`](index/evidence-template.md) for a starting point
- [`index/review-checklist.md`](index/review-checklist.md) for manual submissions
  and audits
- [`docs/maintainer-claim-review-workflow.md`](docs/maintainer-claim-review-workflow.md)
  if the change involves claim state or canonical handoff

The bar for overlay records is not just structural validity. Reviewers should be
able to see what was imported, what was inferred, where build and test commands
came from, and why any `unknown` placeholders remain.

## Protocol changes

If you add or change a schema field, trust rule, CLI/MCP/LSP contract, or public
JSON shape:

- update the relevant RFC or contract doc
- add or update the fixture or contract tests that pin the behavior
- call out compatibility implications clearly in the PR description

## PR expectations

- Describe the user-visible effect, not just the files changed.
- Mention any trust, provenance, or public-surface implications.
- Prefer small, coherent patches over broad cleanup.
- Do not revert unrelated local changes in the worktree.
