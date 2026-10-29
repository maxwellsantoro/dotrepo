# Bounded review: owned synthetic campaign path

**PASS for the owned synthetic end-to-end API/control gate; no blocking finding.** This decision concerns the one new test `scripts/tests/test_agent_campaign_path.py`, SHA256 `58f55900f48129e5119bd08e94c5c2e0cf1f66acee80e4fd8195632141b51592`, reviewed against the unchanged existing runtime/experiment APIs and their fixture helpers. It does not qualify a real task, image, provider, completion oracle, consumer policy or campaign. The reviewer authored the separate applicability diagnostic, not this test.

The new test calls actual `agent_experiment.prepare`, generating randomized 72-session assignment and request artifacts; actual `agent_runtime.load_session` verifies them and loads allowlisted source/arm data; actual `run_session` performs the investigation loop using a fresh `FakeProvider` and `OwnedTaskBackend` for every session. Tool requests/responses, partial wrong actions, final claims and usage come from that runtime's actual owned-simulation execution. A post-run toy scorer reads retained trace events; the test writes trace/scorer/task-gold/task-oracle/rubric-bound scores and observations, then calls actual `summarize`. The returned metrics and all 72 distinct provider/backend identities are asserted.

This is materially stronger than directly supplying 72 fabricated final scores to `summarize`: the assignment, loader, tools, runtime receipts, scorer handoff and summarizer compose in one test. Scoring happens after tool choices; `OwnedTaskBackend.shell` permits and returns a nonzero result for `owned-wrong-scope`, then records the successful recovery. There is no runtime hidden-answer screen. Both arms exercise wrong actions and recoveries, while nonuse/noncompletion remains in the denominator. Pre-clone sessions call checkout through their simulated agent; local sessions use the runtime's starting provision path. Host-side requests omit gold/oracle fields and source-first traces exclude the frozen profile marker. Existing full-freeze validation and content/alias controls remain the underlying isolation checks.

The test explicitly replaces live Docker/provider adapter constructors with fail-fast sentinels. `FakeProvider` and inherited `FakeDocker` have `simulation=True`; all runtime qualification flags are false. Runtime output retains `correctCompletion=None` and `scoringPerformed=False` until this owned post-run scorer acts. No real provider, Docker daemon, upstream test, network or package operation was invoked by the new test or independent replay. Existing narrow suite includes owned subprocess/transport mock controls, not empirical upstream execution.

## Independent checks

The new integration test and existing `test_agent_runtime.py` / `test_agent_experiment.py` suites pass: **223 tests in 5.57 seconds**, exact output in `pytest.log`.

An independent separate invocation of the test captures its final summary, rereads all 72 trace/usage/score/request artifacts and verifies trace/request/usage and score-to-trace bindings. It reconstructs these counts:

| Owned simulated outcome | Source-first | dotrepo-access |
|---|---:|---:|
| Assigned sessions | 36 | 36 |
| Toy completion | 27 | 27 |
| Wrong action retained, with recovery | 9 | 9 |
| Toy direct profile branch | 0 | 9 |
| Toy 404 fallback branch | 0 | 9 |
| Noncompletion | 9 | 9 |

Three additional post-run mutations are rejected by the existing summarizer: removal of an assigned session; changed request hash; cross-session usage reuse. All runtime qualification values remain false. `check.py` and `checks.json` retain this owned replay and its exact refusal reasons. Ruff check/format pass for the new test and independent check; the initial unused import in the review-only checker was removed, with correction retained in `ruff.log`.

## What remains open

The toy lookup payload is deliberately not a real public profile, and the programmed provider does not reason over it. `fixture_score` labels its synthetic branch using HTTP status and retained wrong actions; it is not the reference consumer's value-bound tuple policy, an independent applicability adjudicator, or a real test-event oracle. Its synthetic `incorrectInstructionAccepted` label includes the deliberately wrong source-first action. These are acceptable owned fixture labels for pipeline plumbing; they must not be presented as factual dotrepo instruction errors or consumer results. The separate fixed twelve-task applicability diagnostic is not changed by this test.

The test uses synthetic timestamps and a zero-valued runtime clock. It verifies the existing accounting path's composition, not real latency, contention, enforceable live budgets or model cost estimates. Fresh Python adapter instances are not proof of live container/session/cache isolation. Supplied control observations in the summary ledger are not independent measurements; live checks still require their actual receipts.

Before a real campaign, independently frozen task-specific completion/error oracles and source/context/setup joins, image/cache/network/resource qualification, exact provider/model/settings/prompt and total budget authorization, final campaign consumer/access policy, trustworthy event/usage capture, cleanup and arm isolation must meet their owning gates. Real paid/autonomous sessions and causal benefit remain unperformed. This patch closes no such gate by setting a flag and authorizes no live run.

## Reproduction and retained scope

From `/Users/maxwell/projects/agent/dotrepo`:

```sh
uv run --offline --no-sync pytest -q -p no:cacheprovider scripts/tests/test_agent_campaign_path.py scripts/tests/test_agent_runtime.py scripts/tests/test_agent_experiment.py
```

For independent metadata controls, copy only `check.py` into a new owned directory and run it through `uv run --offline --no-sync python <new-directory>/check.py`; it refuses to reuse its generated `owned-replay` directory. No source fixture corpus or secrets are needed. `source-bindings.json` pins the five inspected code owners. `FREEZE.json` binds this compact review, script, results and logs. Generated pytest/owned-replay fixture directories remain local reproduction outputs, excluded from the review artifact inventory; they are not frozen empirical receipts. No repository file was edited by this reviewer.
