# Independent CI pilot review — 2026-10-29

No actionable finding in the bounded retained-evidence review. The pilot supports
source-attributed workflow context and GitHub-reported job/step conclusions at
three fixed, already exposed development revisions. Its README and assertion
ladder consistently leave command-output corroboration, fresh inner execution,
complete portable setup, consumer applicability and benefit unestablished.
This reviewer has prior E1/F05 development context; this is not a fresh blind or
held-out assessment.

The read-only input is `../pilot-20261029/`, whose `freeze.json` SHA-256 is
`9b936d71ccb748bd46a69bf482ae942cde23de28c936bc6a2f77e6b9e35de8bc`.
No original input was changed. No HTTP request, provider/model call, upstream
command, package installation, index/profile access or workflow run was performed.
The review used retained source bytes, API bodies and local standard-library
hash/structure checks. The acquisition module was parsed, never imported/run.

## Integrity and attribution

[verify.py](verify.py) is an offline rerunnable check:

```sh
uv run python benchmarks/ci-evidence/pilot-review-20261029/verify.py
```

[offline-verification.json](offline-verification.json) records 64 final frozen
file bindings; 19 pre-API file hashes; the declared pre-API timestamp preceding
the first retained request timestamp; 22/30 bounded unauthenticated requests;
1,659,744 response bytes; four exact-head, attempt-1 successful runs; 54 jobs
(47 success, seven skipped); all 829 observed step entries matching raw job
responses; 11 independently recomputed contents-API Git blob hashes; and four
403 log responses. The formatted collector has an identical parsed AST to the
retained executed collector. No redirects, cap overruns or retries with
credentials appear in the retained ledger. These are retained-evidence checks,
not independent authentication of GitHub history or external proof of freeze
creation time.

[integrity.json](integrity.json) additionally records manual command-span and
source/job/step mapping checks. An initial local comparison incorrectly used
camelCase observation timestamp names against raw API snake_case fields; the
checker was corrected and all timestamps then matched. This was a reviewer
checker failure and required no input changes.

## Source challenges

The source paths below are relative to the frozen pilot directory. Their exact
bytes, hashes and line counts are bound by its `source-bindings.json` and the
final freeze; no current upstream file was substituted.

| Case | Sources challenged | Disposition and boundary |
| --- | --- | --- |
| Keras `7efab4a60f5930fa81b0db15ed4ec6e4925e0c45` | `sources/github.com/keras-team/keras/.github/workflows/cpu_tests.yml:22-38,66-145`; `gpu_tests.yml:95-96`; local reusable workflow binding in `actions.yml` and run metadata | Five CPU matrix jobs include a JAX/NNX job that skips the main test step. Applications/wrappers steps are conditional and actually skipped in all five CPU jobs. The other marker, integration and GPU commands have different scopes/conditions. Success is not evidence that the documented unfiltered root suite ran. Optional Codecov token/upload failure policy does not establish a test-secret prerequisite. Mutable images, package resolution, runner hardware and missing NumPy config remain open. These boundaries are explicit in the packet. |
| Compose `343bb382d2192b88d84af49971bb5cb99bee268c` | `sources/github.com/docker/compose/.github/workflows/ci.yml:159-185,295-316`; `Makefile:123-125`; `docker-bake.hcl:93-97`; `Dockerfile:123-141` | The unit step invokes a pinned bake action with target `test`; it is not a literal `make test` observation. The source path to the inner unit recipe is valid, but GHA/BuildKit caches can satisfy work without fresh Go execution. No checkout in that job leaves the action's context semantics outside inspected closure. The six E2E matrix jobs each skip the opposite mode step. Debug/release secret references are separate from unit requirements. The pilot preserves these limits and does not equate unit success with full E2E completion. |
| PhotoCraft `5f9b4391874aabc9deb2fcb905267613e4d93ec8` | `sources/github.com/storytold/photocraft/.github/workflows/ci.yml:120-171,224-244,250-322`; retained `AGENTS.md` and `docs/development.md` | Windows unit/integration shell branches and unit-only doctest condition match their API outcomes. The no-heif command is a partial subset. Corpus fetch/verify and test step success is reported without claiming corpus receipts. The shared gate's command is an input to a mutable reusable workflow, whose historical resolved SHA is retained but implementation/nested composite actions are uninspected. Font/env/cache/toolchain/full-sweep conditions are preserved, and no full-sweep or hardware execution is inferred. |

README comparisons are bounded comparisons to README-level instructions. Much
of this context already exists in the retained contributing/build/development
sources; the pilot explicitly acknowledges that and claims no discovery novelty
from repetition. The all-success run summaries do not suppress skipped jobs or
steps. API success is treated as an attributed conclusion, including where a
single step runs multiple shell commands or an action contains uninspected work.

## Review limits and next evidence

All four log endpoints returned the exact retained 403 message requiring admin
rights. This neither establishes expiry nor test failure. The review cannot
recover test counts, assertions exercised, outputs, cache hits, exact inner argv,
resolved tools/dependencies, secrets use, actual working directory or hardware
state from those failures. It does not establish that the collector's network
policy is a general-purpose safe execution service. The frozen packet is an
observation, not evidence of independent execution or a deployable instruction.

The pilot's proposed next step remains appropriate: authorized exact-run
report/log evidence with collection/skip/cache details and dependency identities,
then separate source/task/environment adjudication. Any later consumer experiment
needs unfamiliar tasks, independent sessions, matched settings and randomized
access; these known cases do not supply generalization or savings evidence.
