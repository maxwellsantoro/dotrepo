# Refresh cadence checkpoint — 2026-10-06

This bounded checkpoint inspected enabled automation, actual workflow runs, PR
#135's lifecycle, retained batch artifacts, and factual record ages on inspected
main `dde2238e951c3912de1bc7cdba05686bef90818a`. It executed no crawler batch,
model requests, upstream build, PR mutation, or publication. The accompanying
[JSON receipt](roadmap-refresh-cadence-2026-10-06.json) retains run identities,
artifact hashes, measurements, and the prepared recovery inputs.

## The latest run was refused because its base changed

`INDEX_AUTOMATION_ENABLED` is `true`. The latest scheduled
[run 37270836657](https://github.com/maxwellsantoro/dotrepo/actions/runs/37270836657)
started at 06:07:26 UTC on October 5 from
`fa830e8ebb1b9bb825e08755f7da2c6c34381dbf`. PR #134 merged at 06:08:21 UTC,
advancing main to `3c3ccd725a20cdbaf1f6502147dfda2e528ec74a` while the batch was
running. The batch crawled and wrote 50 repositories, promoted 20, failed zero,
and made zero model calls. Strict telemetry, index validation, and public-surface
checks passed before PR creation.

[PR #135](https://github.com/maxwellsantoro/dotrepo/pull/135) was then created with
head `e960c0f979f449c2b1a6001ca734635b8df01b53`, whose parent was the older checked
base. At 06:15:18 UTC the initial landing validation failed with
`PR identity, head, or base differs from checked automation input`. This occurred
before exact-head CI dispatch and explains the zero CI checks on that head. The
late guard correctly refused a patch whose tested base no longer matched main.
PR #135 remains open. Its recorded/API-reported base is `3c3ccd7`; inspected main
has since advanced further to `dde2238e`.

Replacing the expected base with a live SHA would invalidate that guard. The
bounded recovery is to regenerate from integrated current main under the same
verification and landing requirements. This checkpoint does not rebase, merge,
or close PR #135.

## Enabled scheduling does not prove successful rotation

The most recent 30 returned runs contain 17 failures, 10 skipped runs, and three
successes. That sample includes historical skipped runs and is not a uniform
30-day window. The latest ten scheduled runs all failed; the daily failure streak
runs from September 19 through October 5. Conclusions alone do not determine
whether index writeback happened.

For example, the October 4
[refresh run 37186895617](https://github.com/maxwellsantoro/dotrepo/actions/runs/37186895617)
successfully passed exact-head [CI 37187202275](https://github.com/maxwellsantoro/dotrepo/actions/runs/37187202275)
and published tested index commit
`b551f27eafc1ca1a3e06ef07181bd75d6da5c248`. Its subsequent
[deployment 37187312664](https://github.com/maxwellsantoro/dotrepo/actions/runs/37187312664)
failed while restoring deployed history with HTTP 403. Index writeback and public
publication therefore need separate dispositions. That is a historical failure;
the archive delivery repair and current public identity are checked separately.
The October 2 and 3 runs failed earlier, at the pre-PR public factual-accuracy
gate (123 assertions across 32 repositories). Causes for the remaining failed
runs were not individually diagnosed here.

The inspected local corpus has 616 records; 562 have factual timestamps at least
14 days old, and the oldest is approximately 19.498 days old. The current age
check can pass the 30-day window while a substantial refresh queue already
exists. This age measurement did not fetch current upstream HEADs. The planner
uses index record membership and `generated_at`, sorts oldest timestamps first,
then limits identities before network inspection. Even an unchanged HEAD is
eligible for inspection after 14 days. Supplementary quality reprocessing also
identifies 554 candidates. Configured capacity of 50 repositories per daily
batch implies a nominal 13-day rotation for 616 records; observed successful
rotation has not been demonstrated by that capacity or freshness result.

## Narrow workflow correction

The workflow now validates a dispatch adjudication budget before sidecars or
materialization. An explicit `adjudication_call_budget=0` skips all model
sidecars and supplies zero to the batch, whose existing helper strips all three
adjudication endpoints at zero remaining budget. Malformed budgets fail at this
first step. Empty dispatch input preserves the existing scheduled provider
policy; the normal verification bar is unchanged.

After strict pre-PR gates, a new preflight reads GitHub's checked default branch
reference and requires it to equal the original `github.sha`. A mismatch or
unreadable reference refuses PR creation and retains a JSON artifact. The
expected base is never replaced with the live value. The original late guards
remain unchanged. This narrows the stale-PR window; it cannot atomically prevent
a main change after preflight, so late exact-base validation is still required.

Focused validation executed the actual workflow budget shell against event
files, the base-check CLI against controlled API responses, and the existing
zero-budget crawler environment helper. All 17 tests passed. Ruff checks and
formatting passed. A read-only live preflight at 04:25:09 UTC confirmed inspected
main `dde2238e` matched the expected SHA. Integrated gates remain the
coordinator's responsibility; no shared Cargo build was run for this packet.

## Prepared bounded regeneration

After tested integration on main and confirmation that archive restore and
publication operate, dispatch a new batch from main with at most five inspected
and five crawled repositories, no discovery, and no model calls:

```bash
gh workflow run index-autonomous-refresh.yml --ref main \
  -f batch_id=refresh-batch-01 -f batch_size=5 -f limit=5 \
  -f adjudication_call_budget=0
```

This command is prepared, not executed. Recheck the current default base at
execution time. Require meaningful source-inspected replacement under normal
fresh verification, strict telemetry, index/public gates, exact-head CI, late
landing checks, snapshot publication, and public identity smoke checks. Keep
failed or partial artifacts, without automatic retries or reuse of the older PR
diff. A successful five-repository run proves one operating refresh path; it
does not prove a full corpus rotation, independent answer correctness, or
consumer usefulness.
