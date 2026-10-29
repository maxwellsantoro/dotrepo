# Bounded successful-tree request reuse

Source patch only: `github.rs` and new test-only child `github/tree_reuse_tests.rs`. Production `fetch_repository_files` creates one local empty tree slot shared by the existing four selectors. The lazy loader fills it only after decoded success; HTTP404 leaves it empty, preserving a later selector's request opportunity. No selectors, ranking, path limits, raw fetches, endpoints, materialized fields, model policy or public API change.

Before evidence: the initial owned HTTP fixture had a URL-base/nonblocking-stream defect and failed before useful measurement (`before.log`); it is retained, not claimed as product evidence. After correcting the fixture and before changing tree loading, the same parity test passed exact selected-path/body/order and actual-counter assertions, then failed the intended tree-count assertion:2actual vs1expected (`before-corrected-fixture.log`). Final production passes this control with1actual tree request. No measured upstream timing or100repository benefit is claimed.

Focused final checks:

- `cargo test --locked --offline -p dotrepo-crawler github:: -- --nocapture`:19pass, including7new owned-localhost tests and existing client/selector/refresh tests (`after-final.log`).
- `cargo fmt --all -- --check`:pass (`fmt-final.log`). The initial pre-format diff is retained separately.
- `cargo clippy --locked --offline -p dotrepo-crawler --all-targets -- -D warnings`:pass (`clippy.log`).

New controls cover selected bytes/order and actual request/header-byte accounting;404then200; decoded-empty success; malformed JSON/500fatal; no eligible selector; separate invocations/repositories/refs; all four selector paths with Rust root-probe behavior unchanged. Calls only target owned localhost fixtures, with no token/default authentication and no proxy. No upstream build/execution, provider, external GitHub or index-writeback action occurred. Cargo slot released to coordinator.

Existing limitations remain: recursive-tree truncation is not an absence proof; nonexistent probes and repeated root Cargo probe remain; response-byte counters use Content-Length; current CLI crawls current heads and cannot be presented as an exact frozen100revision comparison. This optimization is separate from F05 readiness and does not reopen preparation. No source files are committed by the worker. `handoff.json` binds base/current source; `patch.diff` includes the new untracked test file. The coordinator owns independent review, hotspot retain rationale, combined gates and Git.
