# Mechanical context source-binding verifier — development packet

This packet checks the integrity of an existing contextual candidate's attached
sources. It does not establish that the instruction is complete or applicable.
The retained Keras identity is known development material:
`github.com/keras-team/keras@7efab4a60f5930fa81b0db15ed4ec6e4925e0c45`.
The author previously worked on that extractor and its gold. This is neither
held-out qualification nor independent consumer evidence.

`development-plan.json` preserves the initial prepared/unlinked state.
`source-bindings.json` and `source-snapshot/` bind the later integrated code tested
here. The coordinator owns the shared `import/mod.rs` and `fields.rs` wiring;
`shared-wiring.patch` records the requested interface. No extractor, schema,
protocol, crawler, public surface, index record, or confidence promotion changed.

For each candidate carrying `sourceBindingsJson`, the verifier adds exactly one
candidate-specific integrity check. It requires a nonempty JSON array of at most
128 strict rows, an attachment no larger than 128 KiB, contained regular UTF-8
source files read through the existing bounded reader (2 MiB per file), matching
whole-file lowercase SHA256 hashes, and valid inclusive line ranges. Repeated
paths with distinct passages are accepted; exact duplicate spans are refused.
Both declared command and context sources must occur in the checked source set.
The complete candidate value, context source, and assessment/generation time must
also match the attached assessment. Unix leaf and ancestor symlinks are refused
by the existing pinned reader; Windows retains that reader's existing reparse
checks, and this packet does not claim a Windows execution test.

Invalid attached integrity is a `Failure`, makes the whole verification report
fail under existing semantics, and leaves this candidate `Unresolved`. An attached
candidate with no corresponding passing check also remains unresolved. An absent
attachment preserves existing behavior. A successful integrity check leaves the
real Keras route at `MediumConfidencePresent`; hashes and spans say nothing about
prerequisite closure, contextual sufficiency, execution success, or consumer work
saved. The coordinator's separate frozen source disposition explicitly leaves
complete instruction establishment, high promotion, and consumer acceptance false
(freeze SHA256 `2c53e516f15aafe6c80e16aa2b9ff1b104b2537d0a67857052e8f9737303545d`).

Focused checks passed:

- Eight mutation/integration tests: changed/deleted/nonregular/oversized sources;
  malformed/empty/excessive attachments; traversal, row/hash/span defects;
  unrelated valid sources; tuple/source/time mismatch; symlink leaf/ancestor;
  missing/conflicting checks and absent-attachment compatibility; unchanged real
  Keras route with eight passages across five files.
- `cargo clippy -p dotrepo-core --lib -- -D warnings`.
- The two `import_quality_gate` tests on the integrated state.
- `cargo build -p dotrepo-cli --locked --offline`.
- Ruff check and format for the retained local CLI control.

`checks/compile-failed.log` preserves the initial unsupported digest formatting
attempt; the implementation was corrected before the passing focused tests.
`checks/control-correction.json` retains the CLI control's initial incorrect
scalar-absence assumption. No Rust behavior changed for that control correction.
`cli-recovery.json` observes the existing scalar plus one contextual candidate and
all eight bindings. The CLI import command does **not** invoke `verify_import_plan`
or scoring: the core integration tests are the verification/scoring evidence.
No upstream commands, provider calls, containers, or network/index calls ran.

The contract requires a fresh verification against the same unmodified plan and
root before scoring. Files may change after observation; this is not a persistent
filesystem guarantee. Only listed passages are checked, so omitted prerequisites
or qualifications remain possible. A separate source-completeness gate and
independent review remain necessary. This packet makes no acceptance, release,
held-out generalization, or consumer-benefit claim.
