# Fixed F-05 task applicability diagnostic

This known-source operator diagnostic finds **0/12 established direct complete task instructions** in the captured snapshot under the existing contextual reference policy. It finds **4/12 scalar field acceptances**, which must not be reported as four applicable instructions. This is a diagnostic of these retained inputs, not a generalization result, independent consumer trial, task-completion result or causal benefit estimate.

The input declaration was frozen before task/gold comparison: `INPUT_FREEZE.json` SHA256 `e0286bb486ead69935ca3fbcfda526c505573eb0d026a92b12ad437994c4ec6f`, at 2026-10-29 14:54:39.745931 UTC. It binds 69 retained task/request/gold/oracle, capture and policy files, at code revision `b8b7cd0cd76108937db29e965a780d8738757a6d`. Original curator/E1-author context and incidental discovery exposure to embedded profile strings before declaration are disclosed there. No task was selected, removed, repaired or narrowed based on coverage.

## Fixed inputs and policy

All twelve original tasks and revisions remain unchanged: six repository/six component and six pre-clone/six local. The captured immutable snapshot is `bb01b134d0a2d7d913ccf3f0f54327a239d9bce24ac7735259a62bb5630cf976`. Exactly five responses are HTTP200; seven are HTTP404, including empty retained bodies. Input hashes bind original `SOURCE_FREEZE.json`, all twelve original requests/golds/draft oracles, snapshot identity/metadata/receipts and twelve bodies. No live index, new repository source or later source adjudication was consulted.

The exact reference client is `examples/external-consumer/lookup_before_scrape.py`, as loaded by `bench/arms/lookup_first.py`. This diagnostic newly fixes that existing code's policy at the declared revision, evaluating age at each response's retained `observedAt` (06:10:44.851338–06:10:46.372870 UTC), with its existing 30-day bound. **The campaign policy was not already frozen**: the snapshot README explicitly leaves it unfinished. Freezing that final policy remains a campaign readiness requirement. This diagnostic adds no consumer policy or acceptance adapter.

`evaluate_for_task(required_fields=['repo.test'])` measures legacy scalar-field acceptance. It checks metadata, extraction confidence and age; it does not take the enrolled task/component or upstream revision. `select_instruction('test', request={scope,component})` independently measures whole-context selection, with only the task's visible scope/component as constraints. No gold command or prerequisites enter either selector. The latter requires assessed, value-bound context with cwd/scope/prerequisites; it cannot invent these from a scalar.

## All twelve outcomes

“Not established” means a supported complete tuple is unavailable here. It does not assert every displayed command is wrong. Gold dispositions below are the original frozen provisional assessments, not rewritten answers or current campaign-oracle readiness verdicts.

| Task | HTTP | Scalar test / reference acceptance | Task applicability against frozen requirement |
|---|---:|---|---|
| rust-01 Tauri, repository | 200 | `pnpm test` / accepts | Intended Rust repository-default coverage is not established by this package-script scalar. Original gold requires abstention; per-package coverage/setup unresolved. Profile revision differs. |
| rust-02 Sniffnet, `lib/sniffnet-packet-parser` | 200 | `cargo test --verbose -- --nocapture` / abstains | Medium inferred workflow source, also scoped-source refusal. Root scalar carries no component-qualified tuple. Original component gold requires abstention. Profile revision matches. |
| rust-03 Iced, repository | 404 | absent / abstains | Miss retained. Original workflow/environment applicability unresolved. No profile instruction. |
| python-01 MiroFish, repository | 404 | absent / abstains | Miss retained. Original root+backend aggregate instruction requires abstention. No profile instruction. |
| python-02 Home Assistant, `homeassistant` | 404 | absent / abstains | Miss retained. Original primary-package versus aggregate applicability unresolved. No narrower substitution. |
| python-03 youtube-dl, `youtube_dl` | 404 | absent / abstains | Miss retained. Original primary-package versus aggregate applicability unresolved. No narrower substitution. |
| typescript-01 DeepSeek harness, repository | 404 | absent / abstains | Miss retained. Original native-build/platform setup unresolved. No profile instruction. |
| typescript-02 OpenHands, `bin` | 404 | absent / abstains | Miss retained even though original gold offers a provisional complete component alternative. No profile instruction. |
| typescript-03 Vue, repository | 200 | `pnpm test` / accepts | Root test lead only. Complete run-once default project coverage, browser/build prerequisites and runtime are unresolved in original gold. Profile revision differs. |
| go-01 Microsoft TypeScript, repository | 200 | `npm test` / accepts | Not the frozen `npx hereby test` alternative. Equivalence of that scalar alias at the task revision is not established here; no source inspection was performed to invent it. Go/Node/npm/Git and root setup are omitted. Profile revision differs. |
| go-02 Beego, `client/cache` | 404 | absent / abstains | Miss retained. Original cache/backend scope and service setup require abstention. No profile instruction. |
| go-03 Vault, `api` | 200 | `make test` / accepts | Repository-default scalar is not an assessed `api`-module instruction. Treating it as the requested component tuple would discard scope/working-directory/setup uncertainty. Original gold explicitly leaves that equivalence unresolved. Profile revision differs. |

Every hit has **no `testContext` and no `testCandidates`**. Consequently contextual policy selection is 0/5 hits and 0/12 tasks. None of the five profiles contains a complete test prerequisite list or cwd/scope binding. All five have an empty `conflicts` array and pass identity/age checks at capture; absence of reported conflicts is not proof of prerequisite completeness or task correctness. Four hit source revisions differ from the task revision. Revision mismatch is an additional verification burden; the legacy scalar policy itself does not reject it. No equivalence across those revisions was inferred.

The four scalar acceptances divide into three repository tasks and one component task. The component acceptance (Vault) demonstrates the scalar policy's lack of task-scope qualification, not an observed agent mistake. Tauri's Rust coverage and Microsoft's command equivalence remain unsupported rather than independently proven erroneous. Vue remains unresolved. No actual agent accepted an instruction in this diagnostic.

| Denominator | HTTP200 | HTTP404 | Scalar accepted | Complete context selected | Task-supported direct complete tuple |
|---|---:|---:|---:|---:|---:|
| All tasks | 5/12 | 7/12 | 4/12 | 0/12 | 0/12 |
| Repository tasks | 3/6 | 3/6 | 3/6 | 0/6 | 0/6 |
| Component tasks | 2/6 | 4/6 | 1/6 | 0/6 | 0/6 |
| Rust | 2/3 | 1/3 | 1/3 | 0/3 | 0/3 |
| Python | 0/3 | 3/3 | 0/3 | 0/3 | 0/3 |
| JavaScript/TypeScript | 1/3 | 2/3 | 1/3 | 0/3 | 0/3 |
| Go | 2/3 | 1/3 | 2/3 | 0/3 | 0/3 |
| Pre-clone | 3/6 | 3/6 | 3/6 | 0/6 | 0/6 |
| Local checkout | 2/6 | 4/6 | 1/6 | 0/6 | 0/6 |

## Interpretation and checks

The current cohort/snapshot offers scalar leads in four tasks and an abstained root-command lead in a fifth, plus seven explicit misses. Those leads, provenance and negative lookup results might affect investigation/fallback work; this diagnostic does not measure such value. It offers **no established direct complete instruction reuse opportunity** under the contextual policy. That differs from asserting zero possible product value or twelve impossible tasks. No lookup/fallback effort, source verification, execution, final completion, errors by agents, monetary savings or causal effect was measured. All twelve require further source investigation/verification or fallback for a complete applicable instruction under these frozen inputs. Correct policy abstention is observed; “correct abstention followed by successful fallback” is not.

Seven synthetic controls use the exact existing policy functions: a complete high-assessed tuple accepts; a repository tuple is refused for a component request while the scalar still accepts; missing prerequisite member, Medium assessment, record conflict and tuple-command mismatch refuse context; removing context leaves legacy scalar acceptance unchanged. These are policy plumbing controls, never task admission. Existing focused reference-client tests also pass: **25 passed, 60 deselected** (age/extracted acceptance, inferred/scoped refusals and incomplete-command cases). Ruff check/format pass for the sole replay script. No production/frozen file was edited and no network, provider, package or native command was run.

Reproduce using only retained bytes:

```sh
uv run --offline --no-sync python /tmp/dotrepo-f05-applicability-diagnostic-20261029/diagnose.py
```

The command verifies all declared input hashes before replay and prints the per-task observations and seven controls. `replay.json` retains that output, not copies of intermediate HTTP receipts. `FREEZE.json` binds this report, declaration, replay, script and focused check logs. The original receipt/body files remain in their owning packets. This packet does not authorize or launch C2; final campaign policy and task-specific completion/capture/environment gates remain separately owned.
