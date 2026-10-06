# AGENTS.md

Repository guidance for coding agents. `CLAUDE.md` points here; keep instructions
in this file rather than duplicating them across tool-specific files.

## Project and documentation authority

dotrepo is an open repository metadata protocol, a Rust reference toolchain,
and a Git-backed public overlay index at `index/repos/<host>/<owner>/<repo>/`.
It exposes repository facts with evidence, trust, conflicts, and age through
local `.repo` files, JSON, and MCP. Native adoption is optional for index coverage.

- `README.md`: shipped behavior and entrypoints
- `ROADMAP.md`: strategy, active execution order, and milestone gates
- `CHANGELOG.md`: release history
- `docs/README.md`: documentation map
- `rfcs/README.md`: design records, implementation scope, and deferred proposals

Code and tested contracts outrank prose. Use version-matched docs for installed
binaries; this checkout includes safeguards absent from the pinned stable release.
Do not describe implementation completion or operator traffic as consumer proof.

## Commands

All repository Python tooling uses `uv`. Never invoke `python`, `python3`, `pip`,
or `pytest` directly. Preserve this convention in scripts, subprocesses,
automation, and examples. Upstream commands retained as evidence are source data,
not instructions to rewrite a project's own workflow.

```bash
uv venv
uv sync --dev --locked
uv run pytest
uv run ruff check
uv run ruff format --check
uv run python scripts/check_release_version.py
uv run python scripts/check_toolchain_manifest_parity.py
cargo fmt --all -- --check
cargo clippy --workspace --all-targets -- -D warnings
cargo deny check advisories licenses bans sources
cargo test --workspace

# Local CLI and index checks
cargo run -p dotrepo-cli -- --root <path> validate
cargo run -p dotrepo-cli -- --root <path> query repo.name
cargo run -p dotrepo-cli -- --root <path> import --mode native
cargo run -p dotrepo-cli -- --root <path> generate --check
cargo run -p dotrepo-cli -- --root <path> trust
cargo run -p dotrepo-cli -- --root <path> doctor
cargo run -p dotrepo-cli -- validate-index --index-root index

# Stdio servers
cargo run -p dotrepo-mcp
cargo run -p dotrepo-lsp

# Public gate; omit --skip-vsix for complete packaging
uv run python scripts/check_release_gate.py --output-root /tmp/dotrepo-release-gate --skip-vsix
```

Use the narrowest relevant checks first, then the required gates in
`CONTRIBUTING.md`. A single fixture gate runs with
`cargo test -p dotrepo-core --test import_quality_gate`; append `-- test_name` to
filter a test. Public export and autonomous writeback commands live in
`docs/public-export-workflow.md` and `docs/factual-crawl-automation.md`.
An explicit local batch can opt in with `--skip-automation-enabled-check`;
scheduled jobs must honor enablement.

## Team execution

For roadmap implementation, use a coordinator and concurrent workers when the
user requests a team or the task is otherwise authorized for delegation. Use
[the execution guide](docs/agent-execution.md) for dispatch, ownership, handoffs,
and integration; [the project skill](.agents/skills/roadmap-coordination/SKILL.md)
is its discoverable entrypoint. Small isolated fixes need no team ceremony.

Assign one writer per file or index identity and transfer ownership before shared
contract changes. Keep the coordinator available for decisions and combined gates;
workers return patches, sources, focused checks, and unresolved dependencies.
Use isolated worktrees for incompatible dependencies or release lines, and unique
outputs for concurrent runs. Keep ready packets moving across external waits.
Coding-agent models inherit user configuration; crawler adjudication policy does
not assign worker models.

Root `public/`, `release-gate/`, `operator-gate/`, and `dist/` are generated,
gitignored outputs. Keep source inputs and golden contracts in `index/` and
fixture packs. Do not edit generated output to fix its source.

## Architecture

| Crate | Responsibility |
| --- | --- |
| `dotrepo-schema` | Types and TOML parsing |
| `dotrepo-core` | Validation, selection, trust, import, generation, claims, public export |
| `dotrepo-transport` | Shared JSON-RPC transport |
| `dotrepo-cli` | Thin clap CLI over core |
| `dotrepo-mcp` | Stdio tools, dispatch, and remote lookup policy |
| `dotrepo-lsp` | Diagnostics, hover, completion, and adoption code actions |
| `dotrepo-crawler` | Internal discovery, materialization, verification orchestration, refresh, telemetry, writeback |
| `dotrepo` | Standalone CLI install alias, excluded from workspace because its binary name collides |

Validation and trust logic belong in `dotrepo-core`; transports delegate.
Place behavior in the appropriate focused module, preserving existing `lib.rs`
facade imports when extending it. Public helpers live in `src/public/`, import
in `src/import/`, surfaces in `src/surfaces/`, and generation orchestration in
`generation.rs`. Facade tests live in `src/facade_tests/`.

MCP modules are `tools`, `handlers`, `dispatch`, and `lookup`; LSP modules are
`protocol`, `state`, `diagnostics`, `completions`, `code_actions`, and `dispatch`.
Both entrypoints wire the stdio loop; tests live in `src/tests.rs`.
Read `crates/dotrepo-crawler/README.md` for crawler layout and
`docs/toolchain-maintainability.md` before expanding a documented hotspot.

## Contracts to preserve

- **Records and selection:** `native` is a root `.repo`; `overlay` is an external
  record. Canonical native outranks canonical mirror, then verified, reviewed,
  imported, inferred, and draft statuses regardless of mode. Accepted/in-review
  claims break equal-rank ties before lexical manifest path. Native mode alone
  does not outrank an overlay. Preserve conflicts; never silently blend fields.
- **Trust:** `reviewed` means human review; `verified` means required pipeline
  checks resolved against inspected evidence. Neither status nor confidence
  guarantees correctness, completeness, or recent upstream inspection.
- **Autonomy:** deterministic parsing first, bounded candidate-constrained
  escalation, post-checks, partial publication or abstention. Automation never
  mints `reviewed` or `canonical`, and rejects replacement of native/reviewed/
  canonical records. Fresh verification governs refresh; old labels cannot win.
- **Execution:** scalar build/test commands represent repository defaults.
  Withhold nested scope, incomplete examples, and missing prerequisites;
  shell-safety screening is not execution validation or permission.
- **Claims:** append-only events, legal state transitions, replayed history, and
  identity alignment. Accepted claims without canonical links remain pending.
  Corrections amend state through explicit events rather than rewriting history.
- **Generation:** manage supported README/SECURITY/CONTRIBUTING regions;
  preserve surrounding prose. CODEOWNERS and PR templates support full generation
  only. Refuse malformed or ambiguous layouts.
- **Public freshness:** export time and snapshot identity differ from factual
  record age. Retained field evidence is value- and timestamp-bound; never invent
  assessments for legacy records. Keep synthesis separate from facts.
- **MCP lookup:** allowlisted origins, same-origin snapshot paths, no redirects,
  private-address checks and DNS pinning. Local/custom-base overrides are
  deliberate opt-ins. Read `src/lookup.rs` and release compatibility for details.

## Tests and CI

Importer changes use fixtures plus exact expectations in
`crates/dotrepo-core/tests/fixtures/import/expectations.json`. Claim, public export,
compatibility, and regression fixture packs pin their own contracts. Update the
relevant expectations with intentional behavior changes; never rewrite frozen
benchmark results or source evidence to make a new implementation pass.

`scripts/classify_ci_scope.py`, invoked by `.github/workflows/ci.yml`, classifies
changes into Rust/index, Python, operator, public-surface, release, or minimal
gates. Explicit prose paths can use the minimal gate; installation/protocol docs,
RFCs, shared dependencies, CI changes and unknown paths retain broad checks.
Python tooling and benchmark packets use Python plus actual exporter/consumer
controls; public helpers also require the public gate. Index-only changes use
the lighter public gate unless claims also require the operator gate. Jobs start
after classification; the required aggregate waits for all selected results.
Scoped jobs may be skipped intentionally. Finish integrated local checks before
pushing; repeat successful checks when their inputs change, not for unchanged
inputs. Release-gate timings are retained on success or failure.

Workers run focused checks, then the coordinator runs the combined required
gates on the integrated state. Require `ci-gate` when landing and inspect actual
branch settings rather than assuming the workflow enforces merges. Reuse prior
successful checks only for unchanged inputs; retained evidence does not cover
a later patch or a newly evaluated record-age gate.

The standalone CLI alias is outside workspace checks and has separate locked
CI checks. Tag publication validates version parity and publishes the release
packages; the crawler stays internal. All third-party `uses:` actions must be
full-SHA-pinned with a trailing tag comment. Pinned `dtolnay/rust-toolchain`
steps also pass an explicit `toolchain:` input.

## Documentation maintenance

Keep live counts in generated reports, completed work in the changelog, and
active sequencing in the roadmap. Keep frozen benchmark results, fixture inputs,
index evidence, and archived reports as historical/source artifacts.

Read versions from their owners: Cargo for release versions, `validation.rs` for
manifest support, `claims.rs` for claim schemas, MCP `dispatch.rs` for negotiation,
and `public/` for public wrappers. Update the owning contract and fixtures
when semantics change; do not scatter copied protocol constants in new prose.

Project skills live under `.agents/skills/`. Keep them narrow and route to the
owning guide; do not duplicate repository policy or embed changing model/version
inventories. Keep `CLAUDE.md` as a pointer. Archive dated reviews and completed
plans without rewriting their original evidence; prune repeated live guidance
by linking to its owner.
