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

Repository-local tooling resolves paths relative to a declared root and rejects
paths that escape that root after canonicalization. The check reduces symlink
escape risk for existing files, but it cannot eliminate time-of-check/time-of-use
gaps for paths that do not exist yet. Treat containment as a best-effort guard,
not a sandbox boundary, when adding write flows.

Import text inputs have a stricter contract: regular files only, no symlinks
(including contained links), and at most 2 MiB per input. Conventional files,
discovered manifests, workflows, relation discovery, and deterministic deepening
share this reader. Unix opens each descendant relative to a pinned directory
with `O_NOFOLLOW`; Windows rejects reparse paths and opens the leaf without
following it, but concurrent ancestor replacement remains a best-effort limit.
The caller controls the selected root and its ancestors; this is not isolation
against an actor who can move the root itself during import.

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

## Coordinated implementation

Use the [roadmap's execution plan](ROADMAP.md#active-execution-order) to select
ready work and [the execution guide](docs/agent-execution.md) for packet dispatch,
single-writer ownership, handoffs, and integration. Workers run focused checks;
the coordinator runs the required gates on the combined result. External consent,
publication, and observed operating history remain distinct evidence gates.

## Local checks

Create the locked Python environment before running repository tooling. All
Python commands in this repository must go through `uv run`.

```bash
uv venv
uv sync --dev --locked
uv run pytest
```

Start with the affected crate, fixture pack, or script tests while editing.
Finish the integrated patch before pushing: run the selected checks once on that
state, then reuse successful checks only while their inputs remain unchanged.
Superseded PR CI runs cancel automatically; main validation and serialized public
publication remain separate. Keep the actual merged-tree CI check before treating
a main deployment as validated.
Before integrating a toolchain change, run the core workspace checks:

```bash
cargo fmt --all -- --check
cargo clippy --workspace --all-targets -- -D warnings
cargo deny check advisories licenses bans sources
uv run ruff check
uv run ruff format --check
uv run python scripts/check_release_version.py
uv run python scripts/check_toolchain_manifest_parity.py
cargo test --workspace
```

CI separates Rust/workspace checks from Python validation and real
exporter-to-consumer controls. Release and operator checks start after path
classification, concurrently with those jobs, and keep their own required
validation. CI also runs packaging, standalone-alias checks, and stdio smoke
tests. Install `cargo-deny` with `cargo install cargo-deny --locked` if needed.
Require the `ci-gate` check in repository branch protection or rulesets. It runs
after every scoped job and requires each job selected by `change-scope` to
succeed; intentionally skipped jobs are accepted. A missing scope output,
failed classifier, cancelled job, or skipped required job fails the aggregate.
The workflow supplies the check; merge enforcement requires repository settings.
Passing the local list covers the core checks; it does not establish that every
CI job or release artifact passes.

The integration checks follow the changed scope:

| Changed scope | Additional checks |
| --- | --- |
| Explicitly owned prose/root documentation | Formatting, release/toolchain parity, root `.repo` validation; no workspace test rerun |
| Python tooling, tests, or benchmark code/packets | Python suite and actual Rust-exporter/consumer controls; shared dependency changes remain full |
| Maintainer flow or generated surfaces | Native validation, query, trust, doctor, and `generate --check` below |
| Index records, claims, or evidence | `validate-index`; operator gate for claims or evidence semantics |
| Index-only public output | Lightweight public gate: `--skip-release-bundle --skip-vsix` |
| Public Python helpers, hosted Worker, or external consumer | Python and lightweight public gate, including Worker tests and smoke |
| Rust/toolchain, release packaging, installation/protocol docs or RFCs | Complete release gate; include VSIX for packaging completion |
| Standalone alias | Locked alias check; the package is excluded from workspace checks |

```bash
# Maintainer surface checks
cargo run -p dotrepo-cli -- --root examples/native-minimal validate
cargo run -p dotrepo-cli -- --root examples/native-minimal query repo.build --raw
cargo run -p dotrepo-cli -- --root examples/native-minimal trust
cargo run -p dotrepo-cli -- --root examples/native-minimal doctor
cargo run -p dotrepo-cli -- --root examples/native-minimal generate --check

# Index and operator checks
cargo run -p dotrepo-cli -- validate-index --index-root index
uv run python scripts/check_operator_claim_gate.py --output-root /tmp/dotrepo-operator-gate

# Complete packaging and public checks
uv run python scripts/check_release_gate.py --output-root /tmp/dotrepo-release-gate

# Standalone alias checks
cargo fmt --manifest-path crates/dotrepo/Cargo.toml -- --check
cargo check --locked --manifest-path crates/dotrepo/Cargo.toml
```

Use a task-specific output root for each concurrent export or operator gate.
A local `--skip-vsix` run is useful during iteration; record the omission and run
the complete gate before calling release packaging complete. The CI scope
classifier in [classify_ci_scope.py](scripts/classify_ci_scope.py) governs
required merge checks. The prose allowlist is explicit; installation, protocol
documentation, RFCs, shared dependencies, workflow changes and unknown paths
retain broad checks. Mixed changes take the union of requirements; the complete
release gate includes the lightweight public checks. Renames include both old
and new paths, and a failed Git diff fails classification.

Inspect the plan for a committed patch before pushing:

```bash
uv run python scripts/classify_ci_scope.py \
  --base "$(git merge-base HEAD origin/main)" --head "$(git rev-parse HEAD)"
```

This command inspects committed revisions, not uncommitted edits. During iteration,
run the affected tests directly, for example `uv run pytest scripts/tests/test_ci_scope.py`
or `cargo test -p dotrepo-core --test import_quality_gate`. A cached result for an
older patch does not cover a changed input or a newly evaluated freshness window.
The release gate writes `timings.json` and `timings.md` in its output root, including
completed stages before a failure; CI retains them and includes timings in its
job summary. Compare gate wall time and runner usage after scheduling changes;
individual stage times do not include runner queue/setup or artifact-upload time.

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
