# Zellij maintained-default instruction: source assessment

The documented applicability and prerequisite contract are supported for the
unchanged task `e1-rust-01-repository-tests`: `cargo xtask test` from repository
root at `zellij-org/zellij@1f3df933978e00c246553070310175c392fcfe4f`.
There is no discovered source contradiction to that maintainer recipe. This
judgment does not guarantee dependency success on every platform, promote an
automatic assessment to high, or establish consumer benefit.

The command is explicitly listed in CONTRIBUTING. The root Cargo alias, dispatcher
and test implementation bind it to the maintained application-test route. Its
hardcoded list has 19 entries: 12 plugin packages tested together at the host
triple, then 7 nonplugin entries (including root) tested with all features by
default. Two subsequent compile checks cover building without terminal and web.
Cargo's declared workspace has 21 members; `xtask` and `zellij-integration-tests`
are absent from this test list. That limits an **all-workspace** interpretation,
not the documented repository-default interpretation. The task remains repository
scope. No plugin-only, component, bare Cargo, no-web/no-terminal or e2e substitute
is introduced.

The initial plugin-build call does not mean every invocation rebuilds every plugin.
The retained implementation checks force/source timestamps and a target stamp,
and may reuse plugin builds. Proto generation also checks generated-file dates.
The testing route remains unchanged. Successive phases use error propagation;
source describes the intended route, not evidence that every phase completed.

The supported documented setup is Rust 1.95.0 with declared rustfmt/clippy
components and wasm32-wasip1/x86_64-unknown-linux-musl targets, plus protoc,
pkg-config and OpenSSL. The toolchain file supplies the pin; the documentation
names the external tools. Their installation, compatibility and minimum versions
where unspecified have not been observed or invented. Toolchain components/targets
are declared environment configuration, not proof each is exercised in every
phase.

Preserve `.cargo/config.toml`'s target directory and the documented debug-plugin
location under repository `target/wasm32-wasip1/debug`. The maintainer explicitly
warns that `CARGO_TARGET_DIR` takes precedence and breaks debug builds; a target
folder symlink is the documented sharing alternative. Root derivation consults
`CARGO_MANIFEST_DIR`, Cargo selection consults `CARGO`/PATH, and host detection uses
rustc. Applicability assumes those resolve the intended checkout/toolchain; this
source review has not inspected a consumer's overrides or environment.

The configured `x86_64-w64-mingw32-gcc` linker is conditional on target
`x86_64-pc-windows-gnu`. It is not a prerequisite for every Windows target or host,
and the clause does not establish full Windows readiness. Docker/Podman/Compose,
SSH and macOS zig/cargo-zigbuild setup are documented for separate e2e commands;
the inspected default route supplies no call edge requiring that setup here.

The source-gold judgment needs no upstream execution. Exhaustive native/platform
prerequisite sufficiency remains unproven: root Cargo explicitly names
`src/build.rs`, and component manifests/build hooks are outside this selected set.
Those are concrete paths that could affect external-tool/library, generated-asset
or platform conditions, **not discovered missing prerequisites**. Their uninspected
state does not contradict the documented recipe or require withholding its source
applicability judgment. No additional acquisition is proposed. Selected files also
provide no proof that other upstream files are absent. The external xflags parser
implementation was not expanded or run; retained DSL and data structures establish
declared default intentions.

`assessment.json` records 12 assertions with exact source/span hashes and eight
interpretation counterexamples. `source-bindings.json` binds nine retained sources
and both prior packet freezes. `verify.py` checks those bytes/passages, original
gold/result hashes, packet manifests and the independent 19/21 list comparison.
No original proposal, source followup, gold, evaluation, code, docs or index record
was edited.

The assessor is the original proposal/followup author with prior gold and E1
implementation context. This is a known-development followup assessment independent
of extractor/index outputs, not an independent second curator, fresh holdout or
consumer experiment. No network, daemon, package, native/upstream task, provider,
model or Cargo action ran. Automatic establishment/assessment remains separately
gated; this packet grants no high confidence or consumer acceptance.
