# Validation and delivery

[CONTRIBUTING](../CONTRIBUTING.md#local-checks) is the quick start.
[classify_ci_scope.py](../scripts/classify_ci_scope.py) owns required job selection;
[check_ci_gate.py](../scripts/check_ci_gate.py) rejects missing scope outputs,
failed/cancelled jobs and any required job that did not run. Do not maintain a
second path classifier in an agent instruction or a workflow filter.

## Short feedback loops, one integrated gate

Workers run focused checks while changing their owned files. The coordinator
reviews the combined diff, classifies it, then runs the affected integration gates
once. Successful results remain usable only while their inputs remain unchanged.
CI classifies committed changes; local dirty-tree work needs explicit focused
checks until the integration candidate is committed.

```bash
uv sync --dev --locked
uv run ruff check
uv run ruff format --check
uv run python scripts/check_release_version.py
uv run python scripts/check_toolchain_manifest_parity.py
cargo run -p dotrepo-cli -- --root . validate
```

For Python changes, build the native tools used by real subprocess controls first:

```bash
cargo build --locked -p dotrepo-cli -p dotrepo-mcp
uv run pytest --durations=15
```

For core/toolchain changes:

```bash
cargo fmt --all -- --check
cargo clippy --workspace --all-targets -- -D warnings
cargo deny check advisories licenses bans sources
cargo test --workspace
cargo run -p dotrepo-cli -- validate-index
cargo fmt --manifest-path crates/dotrepo/Cargo.toml -- --check
cargo check --locked --manifest-path crates/dotrepo/Cargo.toml
```

CI additionally checks six publishable crates with `cargo publish --dry-run`,
native write boundaries on both Linux and Windows, MCP/LSP stdio and the
maintainer surfaces. The standalone alias is outside workspace checks. Full
release validation includes the native bundle, VSIX and browser presentation;
the lightweight public gate omits packaging only:

```bash
uv run python scripts/check_operator_claim_gate.py --output-root /tmp/dotrepo-TASK/operator
uv run python scripts/check_release_gate.py --output-root /tmp/dotrepo-TASK/release
# Public-only scope, not a packaging receipt:
uv run python scripts/check_release_gate.py --output-root /tmp/dotrepo-TASK/public \
  --skip-release-bundle --skip-vsix
```

Replace `TASK` with a unique task/run name. Concurrent workers need disjoint
outputs and, when dependency states differ, separate worktrees and absolute
`UV_PROJECT_ENVIRONMENT` paths. Do not share a writable Cargo target between
simultaneous gates. One coordinator can own a warmed target and sequence the
combined builds; separate targets trade disk/build work for concurrency.
Some release packaging tools expect the checkout's default `target/`, so do not
redirect `CARGO_TARGET_DIR` for the complete release gate without checking it.

## CI scheduling and caches

Jobs start together after path classification. Only superseded PR runs cancel;
main validation and serialized publication retain their own results. Mixed paths
take the union of requirements, with the complete release gate subsuming the
public-only gate. Explicit coordination prose/skill metadata takes the minimal
route. New skill executables, unknown files, protocol/install docs, CI policy and
shared dependencies stay broad. Deletions and both sides of renames count.

Caches accelerate execution; they are not acceptance evidence. Browser cache
keys bind OS, architecture and Playwright version. The cached binary is launched
on the current runner before presentation QA. If it fails, the preflight attempts
one dependency installation and requires a successful second launch. Installer
failure or persistent launch failure fails the job. This avoids assuming that a
cache contains another runner's operating-system libraries. See
[Playwright's CI guidance](https://playwright.dev/docs/ci#caching-browsers).

The release gate retains stage timings even on failure. Measure whole-job and
queue time separately from stage timings; extra concurrency can reduce elapsed
time while increasing runner cost. Preserve meaningful tests and failure
propagation before claiming a faster lane.

## Publication remains a separate gate

The current default-branch source must match the exact successful main CI event,
and publication rechecks it before mutable actions. The workflow preserves
freshness validation, append-only history, complete R2 archival before promotion,
and served-output verification. Manual dispatch does not waive these controls.

Do not skip a deployment based only on the most recent commit's paths: a prior
code change may have been superseded before publication, then followed by prose.
A future no-op publication check must compare with an actual verified published
source, include all intervening changes, and conservatively publish on unknown
or unavailable evidence. This review does not introduce a new production receipt
format or weaken archival checks to obtain that optimization.

The November 4 baseline illustrates the priority: PR223's longest validation
job was 168 seconds; main's was 158 seconds. The successful public deployment
took 830 seconds, including 636 seconds for archival and 68 seconds for restore.
These are observed job durations, not a measured speedup from this change.
[PR CI](https://github.com/lazy-collective/dotrepo/actions/runs/41934146483),
[main CI](https://github.com/lazy-collective/dotrepo/actions/runs/41934678076),
[publication](https://github.com/lazy-collective/dotrepo/actions/runs/41935120362).
