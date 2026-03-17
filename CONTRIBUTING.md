# Contributing to dotrepo

dotrepo is a protocol, a reference Rust toolchain, and a seed public index.
Contributions are welcome across all three, but the standard is reviewable,
tested changes rather than speculative surface area.

## Where to contribute

- Protocol and schema: changes to `.repo`, trust semantics, claim flow, or the
  public JSON contracts.
- Toolchain: CLI, MCP, LSP, import, validation, generate-check, docs, and
  release workflow improvements.
- Seed index: evidence-backed overlay records under `index/`.

## Before you open a PR

- Read the shortest relevant doc first instead of starting from the full RFC
  set. Use [`README.md`](README.md) for the main entry points.
- If you are changing the protocol shape or a public contract, update the
  corresponding RFC or contract doc in the same patch.
- Keep trust, provenance, and conflict surfacing explicit. dotrepo should not
  silently flatten competing records or overstate confidence.

## Local checks

Run the core workspace checks:

```bash
cargo fmt --all -- --check
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

If you touched the seed index, claims, or evidence rules, also run:

```bash
cargo run -p dotrepo-cli -- validate-index --index-root index
python3 scripts/check_operator_claim_gate.py --output-root /tmp/dotrepo-operator-gate
```

If you touched public export, release packaging, or the hosted Pages surface,
also run:

```bash
python3 scripts/check_release_gate.py --output-root /tmp/dotrepo-release-gate --skip-vsix
```

## Seed index contributions

Overlay submissions live under:

```text
index/repos/<host>/<owner>/<repo>/
  record.toml
  evidence.md
```

Use these repo-local docs together:

- [`index/README.md`](index/README.md) for the seed index layout and evidence rubric
- [`index/evidence-template.md`](index/evidence-template.md) for a starting point
- [`index/review-checklist.md`](index/review-checklist.md) for the merge bar
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
