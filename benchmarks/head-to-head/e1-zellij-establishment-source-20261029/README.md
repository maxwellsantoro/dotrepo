# Zellij default-test flag and metadata source follow-up

This source-only packet preserves the original task and command:
`e1-rust-01-repository-tests`, `cargo xtask test`, repository root, at
`zellij-org/zellij@1f3df933978e00c246553070310175c392fcfe4f`.
It is a known exposed supported-miss development case, reviewed by a prior E1
author with project/gold context. It is not fresh qualification or consumer use.

The prefetch declaration binds the earlier proposal freeze, retained main source,
two exact requested paths/arguments and limits. Main has plain `mod flags;` and
`mod metadata;` declarations at lines12/15. A before-fetch locator correction
preserves an initial off-by-one transcription; source hash and requested paths
never changed. Only `xtask/src/flags.rs` and `xtask/src/metadata.rs` were requested.
Both resolve at the exact ref. Two GitHub connector reads acquired 14,942 bytes;
returned Git blob identities match locally recomputed identities. No tree walk,
additional file acquisition, or generated-module search occurred.

The flag source contains the xflags DSL and checked generated data structures.
The `test` command declares optional web/terminal opt-outs and arguments forwarded
after `cargo test --`. Separate subcommands handle CI e2e and in-process
whole-application integration tests. The unchanged command requests neither
opt-outs nor additional filters. The external macro supplies parser implementation
methods not expanded in this packet; these are declared flag/default intentions,
not values observed by executing the upstream parser.

The metadata helper queries `cargo metadata --format-version 1 --no-deps`, maps
`.` to root package `zellij`, and chooses optional-feature subsets from root
default features that a package owns, excluding the specified features. It does
not own or dynamically enumerate the test member list. The retained main's hardcoded
list has 19 entries; root `Cargo.toml` declares 21 workspace members.
`xtask` and `zellij-integration-tests` are absent from the test list. Thus the
maintained default route is not a claim that every Cargo workspace member is tested.
These counts come from literal source-data comparison, not Cargo execution.

The default test body aggregates plugin packages, iterates non-plugin entries with
normal all-features behavior, then separately checks whether terminal and web
features can be disabled. Those compile checks do not imply that default tests
omit terminal/web. Adding `--no-web`, `--no-terminal`, a component selector or an
e2e subcommand would change the original task and is not proposed.

Eight claims in `disposition.json` bind exact passages and remaining questions.
The original Rust pin/components/targets, protoc/pkg-config/OpenSSL setup and
target-dir constraint remain intact, including the Windows GNU linker clause
`x86_64-w64-mingw32-gcc`. Tools, platform readiness, dependencies/caches, consumer
config/env overrides and execution success were not observed. The root assessor
must independently decide whether the documented setup establishes applicability;
this packet supplies no confidence promotion, implementation or protocol rule.

`verify.py` checks raw request/source identity, retained source hashes, claim
passages and the member-list comparison without executing upstream code. It and
Ruff check/format pass. No `index/` files, original gold/results, shared code/docs,
packages, Cargo, native/upstream commands, containers or model/provider calls were
modified or run. No further acquisition or closure is proposed.
