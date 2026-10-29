# Go workflow association amendment 1 — 2026-10-29

This append-only amendment corrects the two independently reproduced association
issues in the original Go guard. The original author packet, freeze and reviewer
findings remain unchanged. This is development/regression evidence on known F1
sources and owned synthetic controls, not held-out qualification, upstream
execution or consumer benefit.

Only `crates/dotrepo-core/src/import/commands/go_context.rs` and its focused test
module changed relative to the original handoff. The other four Rust paths and
all six fixture directories retain their original bound bytes. The coordinator
separately appended the supplied fixture expectations. `source-bindings.json`
binds those states, the prior packets and the actual rebuilt CLI;
`amendment.patch` is the delta against the independently retained original source.

## Corrected source association

Supported plain, single-quoted and double-quoted mapping keys now share a private
structural view. The view treats literal/folded scalar bodies as data; those
bodies cannot introduce jobs, steps, services, actions or directory properties.
Directory declarations are associated only with workflow/job `defaults.run` or
an actual step property. Job services and step `uses` likewise need their actual
structural positions. Arbitrary env/name/config text is not an execution field.

Directory precedence is step, then job default, then workflow default. An actual
step `working-directory: .` overrides a nonroot default. A later nonroot `cd` in
that same run still changes observed scope; it is not erased by the earlier root
setting or by `cd .` after the change.

Only associated supported `run` values are read as command lines. Literal run
bodies are separate from YAML properties. Bounded shell heredoc bodies are data,
so fake directory/service/action fields, Go tests and Redis commands inside them
do not count as declarations or invocations. Actual commands following the
terminator remain visible. The parser does not execute or evaluate shell code.

Recognized unsupported flow mappings, aliased job/step/run forms, dynamic run
expressions, folded run bodies, escaped/multiline run quoting and unclosed
heredocs retain explicit uncertainty. They cannot silently restore a conventional
Go scalar through the ordinary adjudication ladder. This remains a bounded
structural screen, not a general YAML/shell implementation. Common simple quoted
keys are supported; arbitrary YAML quoting/tag/anchor semantics are not claimed.

## Checks and observed behavior

The final commands/context suite passed **69 tests**, including **18 Go tests**.
New controls exercise:

- Plain/single/double quoted jobs, steps, services, actions, run and directory keys.
- Literal/folded non-run data in workflow env, job env, step name and step env,
  containing fake jobs/steps/uses/services/working-directory declarations.
- Heredoc data versus actual following directory/service/test commands.
- Workflow/job/step directory precedence and separate later `cd` behavior.
- Explicit uncertainty for the supported detection of unknown structures.
- Eight full importer scenarios through actual escalation at budgets 0 and 2,
  retaining blocked fields as unresolved and recording zero provider calls.

`escalation-controls.json` retains all **16** importer/escalation observations.
The original IBM/Redigo, explicit-maintainer, unrelated-job/example/ecosystem and
candidate-preservation controls continue to pass. No existing source fixture was
rewritten to obtain this result.

The rebuilt first-party CLI repeated the reviewer's six original synthetic
imports. The root control still supplies both defaults; plain and quoted service
variants supply build while withholding test; workflow/job literal environment
data now leaves both defaults available. `cli-controls.json` retains exact
workflows, argv, manifests and evidence. These are local importer operations on
owned `/tmp` fixtures, not third-party test execution or consumer measurements.

The integrated fixture gate passed **2 tests**, core-library Clippy passed, and
the CLI built with `--locked --offline`. Owned Rust formatting, Python Ruff/check
format, whitespace and source/fixture hash checks passed. No full workspace or
release gate was run by this worker. Cargo was released before reviewer retesting.

Raw attempts are retained under `checks/`: the first amendment compile found an
explicit lifetime omission; a later compile found an unsupported string-pattern
array. Both were corrected, and the final successful runs are separately retained.
A readonly reviewer identified flow job/step association cases during preparation;
those became conservative unknown-structure controls before this final freeze.

## Limits

Redigo build/default evidence remains the separate open decision described in the
original packet. This amendment does not execute workflows, infer all service
prerequisites, interpret arbitrary shell programs, expand workflow aliases or
reusable calls, prove every YAML/shell form safe, change the evidence protocol,
create tombstones or mutate index records. Detected uncertainty withholds scalars;
an untriggered guard is not proof of complete scope/setup. Explicit maintainer
selection retains the existing source-tier policy and no new confidence/status
is minted.

The structured view is purpose-built for these conservative Go refusal checks;
other importer command extraction remains unchanged. Independent amendment
retesting and coordinator combined gates remain required before landing. No
network, paid provider, model, upstream code, Docker or index operation occurred.
