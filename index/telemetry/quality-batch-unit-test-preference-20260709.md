# Quality batch — unit-test preference (2026-07-09)

## Parser changes (`dotrepo-core` import commands)

1. Prefer Makefile/justfile targets `unit-test` / `test-unit` before composite
   `test` so one-line unit suites unwrap (`go test ./... -short`) instead of
   `make test` multi-step integration chains.
2. Prefer Makefile over justfile when both publish task-script commands for the
   same field (dual-maintainer Go surfaces).
3. Reject specialized Go CI workflow tests with `-args`, coverprofiles, or
   `gocoverdir` so they cannot become `repo.test` after task-script conflicts.

Regression tests in `import/commands/mod.rs`:
- `makefile_unit_test_target_outranks_composite_test`
- `makefile_preferred_over_justfile_on_task_script_conflict`
- `specialized_go_ci_coverdir_is_not_a_workflow_test_command`

## Index disposition

- `github.com/jesseduffield/lazygit`: recrawl after parser fix →
  `test = "go test ./... -short"` (evidence from Makefile `unit-test`), status
  remains `verified`. Prior path had Makefile/justfile conflict then CI
  coverdir escalation.
- Coverage-gap recrawl sample of empty-script JS packages and polyglot tools
  reconfirmed honest absence (no invented build/test).

## Counts

Missing build/test remained **221/226** at corpus size 613 after the batch:
fill rate did not vanity-improve; command *quality* improved for dual
task-script Go layouts.
