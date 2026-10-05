# Controlled task-observation packet — 2026-10-05

This is an operator rehearsal of measurement plumbing, not an independent
holdout, upstream execution, or product-benefit result. Source selection is
scripted from the local project under `../../task-fixtures/project`.

The workload was written before requesting profiles from the local HTTP fixture
server. Ten tasks ran in both arms with alternating order and a fresh project
copy for every attempt. `cold` means no application response cache; OS/process
caches were not controlled. No model was invoked. The model/cost fields are not
instrumented and remain null; maintenance allocation remains null.

- Both arms completed ten tasks.
- Lookup-first accepted five instructions, including two deliberately wrong
  controls. These caused two failed attempts; fallback then completed the tasks.
- Five policy rejections completed through correct source fallback.
- The source arm made ten actual loopback HTTP requests; lookup-first made
  seventeen, including fallback. Timings are machine-specific fixture timings.
- Every attempt retains command/context, exit status, oracle result, stdout,
  stderr, and a digest binding in `observations.json`. Successful compilation
  exits zero while its completion oracle remains false.

`workload.json`, `observations.json`, and `logs/` are frozen inputs. Re-score into
a separate output directory with `bench.tasks`; run a new local rehearsal with
`bench.task_reference` into a new directory. Preserve this packet's inputs and
results. The scorer's negative tests copy the packet before mutating it.

The external workload still requires participant-selected repositories, exact
Git revisions, reviewed source evidence and success oracles. Supplied log hashes
prove consistency, not independent observation or external adoption.
