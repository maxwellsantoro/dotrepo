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

Use `uv` for repository Python tooling. Start with the affected test or crate,
then run the checks selected for the combined patch once its inputs settle:

```bash
uv sync --dev --locked
uv run pytest scripts/tests/test_ci_scope.py  # Example focused feedback loop
uv run python scripts/classify_ci_scope.py \
  --base "$(git merge-base HEAD origin/main)" --head "$(git rev-parse HEAD)"
```

The classifier inspects committed revisions, including both sides of renames.
During uncommitted work, choose the affected tests directly. Unknown paths and
changes to the classifier itself require the full gate; a failed diff is an error.

| Change | Integrated acceptance |
| --- | --- |
| Explicit prose and coordination skill metadata | Ruff, release/toolchain parity, root `.repo` validation |
| Python tools/tests | Python suite, native exporter/MCP build and actual consumer controls |
| Index records / claims | Index validation and public gate; claims also require operator gate |
| Public rendering, Worker or external consumer | Python and public gate, including Worker tests and smoke |
| Release packaging helpers / VS Code extension | Python and complete release gate, including native bundle and VSIX |
| Rust, protocol/install docs, shared dependencies or CI | Core, native write boundaries on Linux/Windows, Python and complete release gate; core/schema/CLI/shared/unknown scopes also run operator gate |

[CI and validation](docs/ci.md) owns the exact commands, scheduling, cache and
publication rules. The [classifier](scripts/classify_ci_scope.py) owns required
job selection. The stable `ci-gate` must pass for the exact PR head; a local
subset or successful worker handoff is not the integrated gate. Packaging is
complete only after the native bundle and VSIX checks; `--skip-vsix` is iteration
feedback, not a release receipt.

For concurrent work, use task-specific output roots and Python environments.
Only one owner should run builds against a shared Cargo target directory. Reuse
successful checks only when their inputs are unchanged; rerun the affected gates
after integration edits or a newly evaluated freshness window. Preserve failed
attempts beside the final evidence. See [agent execution](docs/agent-execution.md).

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
