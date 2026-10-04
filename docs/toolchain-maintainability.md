# Reference toolchain maintainability

The CLI, MCP, and LSP are thin transports over `dotrepo-core`. Extend core
behavior first, preserve facade imports, and put new work in focused modules.
Product priorities live in [the roadmap](../ROADMAP.md#active-execution-order).

## Current layout

| Area | Source and responsibility |
| --- | --- |
| Core facade | `src/lib.rs` re-exports domain APIs; `src/facade_tests/` covers selection, public, claims, import, surfaces, validation, and relations |
| Import | `src/import/`: inputs, types, evidence, fields, toolchain, write; `commands/`, `parsing/`, and `escalation/` separate extraction, policy, and model routing |
| Public API | `src/public/`: types, profiles, evidence, search, compare, relations, export, PageDigest, errors |
| Generation | `generation.rs` shares output planning across generation, drift checks, and previews; `surfaces/` owns file states and renderers |
| MCP | `tools.rs`, `handlers.rs`, `dispatch.rs`, `lookup.rs`; `main.rs` wires stdio, `tests.rs` and `test_support.rs` exercise parity |
| LSP | `protocol.rs`, `state.rs`, `diagnostics.rs`, `completions.rs`, `code_actions.rs`, `dispatch.rs`; `main.rs` wires stdio, `tests.rs` covers server behavior |
| CLI packages | Workspace and standalone alias binaries call `dotrepo_cli::main()` / `run()` |
| Crawler | [Crate guide](../crates/dotrepo-crawler/README.md); `pipeline/` separates merge, evidence, writeback gate, and synthesis |

Completed extraction history belongs in [the changelog](../CHANGELOG.md), not a
second task list here. Rustdoc examples cover high-traffic repository entrypoints;
expand them when extending batch/public APIs.

## Hotspot dispositions

Every reference-toolchain Rust source above roughly 1,500 lines needs a split
plan or explicit retain rationale. The October 3 source audit found these three
above the threshold; counts are diagnostic snapshots, not permanent baselines.

| File | Disposition |
| --- | --- |
| `crates/dotrepo-crawler/src/github.rs` | 1,596 lines. Split before the next materialization/API feature: `github/client.rs` for HTTP/auth/rate limits; `discovery.rs` for discovery/refresh candidates; `materialize_paths.rs` for root/monorepo selectors; `types.rs` for DTOs; `mod.rs` preserves client re-exports. |
| `crates/dotrepo-cli/src/tests.rs` | 1,610 lines, test-only. Split by CLI command domain when adding the next test family. |
| `crates/dotrepo-core/src/facade_tests/import_repository.rs` | 1,608 lines, test-only. Split evidence, escalation, and assembly domains on the next import-fixture expansion; parsing already has its own module. |

The command orchestrator's unit tests now live in `import/commands/tests.rs`,
keeping `mod.rs` focused on loading and assembly. `claims.rs` remains near the
threshold. Check sizes when expanding them; do not rely on former counts.
Refresh the inventory with:

```bash
uv run python - <<'PY'
from pathlib import Path
for path in sorted(Path("crates").glob("*/src/**/*.rs")):
    lines = len(path.read_text().splitlines())
    if lines > 1500:
        print(f"{lines:5} {path}")
PY
```

Facade domains can run independently, for example
`cargo test -p dotrepo-core --lib tests::selection`.

## Operational maintainability

Index size does not establish operational health. Use growth/freshness reports,
coverage and accuracy gates, risk-weighted audit dispositions, and retained
unit-cost telemetry. Release floors gate validity, completeness, accuracy, and
record age; verified/high-signal counts are advisory rather than incentives to
inflate authority. See [crawl operations](factual-crawl-automation.md) and
[measurement interpretation](public-lookup-efficiency-benchmark.md).
