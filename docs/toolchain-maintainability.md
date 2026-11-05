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

Use these known boundaries when a selected packet expands the affected code.
File size is a diagnostic, not a separate refactor gate: split when it removes
ownership contention or makes the changed behavior easier to verify. Do not
delay a bounded workflow for unrelated cleanup. The table retains the October 3
audit's suggested boundaries; inspect the current source before assigning work.

| File | Disposition |
| --- | --- |
| `crates/dotrepo-crawler/src/github.rs` | HTTP retry/timeouts and their fault-injection tests are extracted to `github/http.rs` and `github/http/tests.rs`. For materialization/API work, consider separate owners for: client/auth setup, discovery/refresh candidates, materialization selectors and DTOs, with the existing facade preserved. |
| `crates/dotrepo-cli/src/tests.rs` | Test-only; CLI command domains are a natural boundary when adding a new test family. |
| `crates/dotrepo-core/src/facade_tests/import_repository.rs` | Test-only; evidence, escalation and assembly can be separate domains on an affected import-fixture expansion; parsing has its own module. |

The command orchestrator's unit tests now live in `import/commands/tests.rs`,
keeping `mod.rs` focused on loading and assembly. Check current source when
expanding a module; do not treat historical sizes as a current inventory.
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
record age; checked/high-signal counts are advisory rather than incentives to
inflate authority. See [crawl operations](factual-crawl-automation.md) and
[measurement interpretation](public-lookup-efficiency-benchmark.md).
