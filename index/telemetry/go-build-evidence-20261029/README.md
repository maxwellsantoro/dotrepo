# Go build instruction eligibility — October 29, 2026

Root `go.mod` metadata no longer supplies a repository-default build scalar by itself. Its `go build ./...` candidate remains in raw diagnostics and unresolved evidence, but is ineligible for selection and actual adjudication requests. The Go test policy is unchanged. This closes the remaining Redigo metadata-only build recurrence at the importer boundary without a protocol, tombstone, prior-record veto or repository-name special case.

The baseline is `df4252056ce18dec6a13d5e84706c2ae48a13a2d`. The coordinator subsequently advanced branch metadata to merged PR187 at `72c654caaba1c88a7206815296bec91fa3bb5760`, with source content unchanged before this patch. `source-bindings.json` SHA256 `9c8aa806bb7e2077c8f8c1c0ea1dfa4c3e8687e2359225ce616030b723a62849` and `implementation.patch` retain the tested eligibility implementation. Those bindings precede the coordinator's later independent E1-verifier wiring in shared `fields.rs`/`import/mod.rs`; they have not been rewritten to claim coverage of that later integrated source.

## Behavior and ownership

The worker changed only `commands/mod.rs`, `commands/go_context.rs` and its test module. The coordinator applied the small shared `fields.rs` eligibility call, updated the reserved facade regression, and reconciled four live fixture expectation rows from the supplied patches. No fixture input, index record or frozen historical packet changed.

One source-tier/path predicate rejects only build candidates from root `go.mod` at EcosystemDefault tier. It is shared between the selection copy and `build_adjudication_requests`; the latter cannot offer a retained raw module build when a separate workflow or declaration is later suspect. Explicit Manifest, ContribDoc and TaskScript candidates remain eligible. Original scope/setup/unsupported-context refusal is evaluated first and retains its existing field-wide blocking behavior. A separate metadata-only flag blocks the field only when no filtered build alternative remains.

The four golden rows affected are `f1-go-service-context`, `f1-go-unrelated-service-context`, `f1-go-example-module-context` and `f1-go-services-block-context`. Their build becomes null; test values do not change. Losing a selected inferred build also removes its inferred-field/provenance contribution. In the exact Redigo fixture this changes overlay status from inferred to imported because only imported fields remain; neither reviewed nor verified status is minted. One imported-source order changes because workflow test selection now precedes the module's toolchain evidence. Existing IBM unresolved fields and explicit-maintainer defaults remain unchanged.

## Checks and retained failures

Final focused evidence, retained under `checks/`:

- 71 command/context tests passed, including 20 Go tests.
- The existing facade regression passed with selected build None, raw candidate retained, Unresolved scoring and no build adjudication request.
- Both import-quality gates passed with the deliberately reconciled expectations.
- Core all-target Clippy, repository formatting check and whitespace check passed.
- Twelve new real importer/escalation controls exercise six cases at budgets 0 and 2: metadata-only evidence, ordinary root workflow observation, exact tagged workflow variant, specialized release filename, scoped workflow and explicit CONTRIBUTING build. They report zero model calls.
- Six existing F1 escalation controls and sixteen association controls at budgets 0 and 2 continue to pass with unchanged Go test expectations. `control-receipts.json` extracts their actual emitted JSON; raw logs remain authoritative.
- Two request-level conflict controls preserve conflicting explicit alternatives without a scoped workflow, reject raw go.mod from those requests, and retain the original whole-field refusal when an actual scoped workflow exists.

The first compile exposed internal candidate versus public summary types at the shared helper call; the predicate was changed to accept source path/tier metadata. A later test compile omitted unwrapping optional trust notes. The first quality check exposed imported-source ordering, and the first format check required wrapping the coordinator's helper call. Each failure is retained separately from its successful final check.

Independent review also captured a real before-fix CLI import for conflicting README and CONTRIBUTING instructions: the initial implementation incorrectly combined the genuine conflict with a metadata-only whole-field block. That immutable receipt is `index/telemetry/go-build-evidence-review-20261029/before-conflict/freeze.json` SHA256 `d160760b719b427b9b78af6c6563f83b4c11bf367fa5807c9ae4bb31495f0cc7`. The CLI did not expose requests directly; the source-based request suppression inference and that limit belong to its reviewer packet. The final two request controls verify the separate-flag correction directly. No original scope/setup block was relaxed.

## Source and policy limits

`input-source-bindings.json` verifies all 22 existing fixture input hashes against the prior Go amendment and all 11 retained Redigo source/metadata hashes against the original F1 freeze. Redigo revision remains `57c8b99ccb90c3401bec6e09289081e8b78b3bde`. Its README describes go-get installation and its release workflow invokes GoReleaser; neither establishes the bare command as a developer-default build. The command may compile the library after suitable setup. This patch withholds an unsupported scalar assertion; it does not prove runtime failure.

Removing the module build normalization target preserves an ordinary `ci.yml` tagged build as its exact inferred Workflow command instead of silently replacing it with bare `go build ./...`. The focused control deliberately records that interaction. Existing workflow admission of specialized build variants, maintainer-default intent and full prerequisites remain separate unresolved policy/evidence questions. An accepted workflow observation or an untriggered context guard is not execution validation or complete default-instruction proof. No workflow corroboration rule was introduced.

This is a known development/regression packet, not held-out qualification, fresh blind evaluation or consumer benefit. No new source/package acquisition, network/provider calls, third-party builds/tests, index writes or status promotion occurred. First-party Rust tests/import operations used owned synthetic inputs or retained fixture bytes. Independent final retest and coordinator combined gates remain required before landing; this packet claims only its exact focused bindings.
