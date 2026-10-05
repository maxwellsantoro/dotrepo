# Generic agent integration pilot

This package is ready for an external team to integrate. No participating team or
independent adoption is claimed. A deployment by the dotrepo operator remains
operator evidence even when it uses this package.

## Deliverables

- Dependency-free HTTP client: `examples/external-consumer/lookup_before_scrape.py`.
- MCP equivalent and setup: `docs/external-consumer-integration.md`.
- Executable fallback experiment: `lookup-first` arm in `benchmarks/head-to-head`.
- Structured outcome template: `examples/external-consumer/pilot-report.example.json`.
- Paired task scorer and controlled rehearsal:
  [task observation contract](../benchmarks/head-to-head/task-fixtures/README.md).
- Reviewable [invitation draft](../examples/external-consumer/pilot-invitation.md);
  it has not been sent and does not identify a consenting participant.

## Preparation and handoff

Follow the [roadmap](../ROADMAP.md) for start conditions and priority. Prepare
these independently owned outputs in parallel before an external team is ready:

| Package | Reviewable output | Dependency |
| --- | --- | --- |
| Workload and rubric | Frozen tasks selected before checking index coverage; upstream answers and task-success rubric with source/check dates | No consumer deployment required |
| Integration adapter | Bounded lookup, identity/age/conflict checks, upstream fallback, and outcome telemetry exercised with fixtures | Use the existing [consumer policy](external-consumer-integration.md#positive-command-acceptance) |
| Measurement harness | Source-first and lookup-first runs with cache state, actual usage, fallback work, and maintenance-cost allocation | Freeze the rubric before scoring |
| External handoff | Consenting team, deployed integration URL, observation window, and retained outcome report | Authorized outreach and a participating team |

The coordinator fixes the workload and policy versions, checks adapter/harness
compatibility, and integrates the results. Keep unfavorable tasks and unresolved
costs visible. A blocked external handoff need not block fixture-backed adapter
and harness work. Reference runs remain operator evidence.

The task scorer validates workload/log hashes, paired order, revision/environment,
context preservation, and observed completion separately from policy acceptance.
Its retained controlled runs include accepted wrong instructions and fallback
recovery. Supplied log hashes prove consistency, not independent observation;
participant task oracles and outcomes need review before the C2/C3 gates close.

For lookup and command acceptance, use the
[integration contract](external-consumer-integration.md). Record the final task
outcome as well as lookup and fallback results; a 200 response is not task success.

## Pilot design

Freeze a representative task list before looking at index coverage. Include
unindexed repositories and multiple ecosystems. Alternate source-first and
lookup-first runs, declare cache state, use the same task-success rubric, and
report errors, abstentions, and fallbacks separately. Do not remove unfavorable
tasks after inspecting the results.

Record HTTP requests, decoded response bytes, wall time, actual model token usage
where available, and allocated index maintenance cost. Unknown costs remain null,
not zero. Bytes divided by four is not billed model usage. The benchmark's
`transport` counts include prefetch and fallback HTTP work; `elapsedMs` includes
the whole arm. Legacy per-field latency excludes model inference.

## Acceptance

An independent pilot needs a named consenting team, a deployed integration URL,
a stated observation window, a frozen workload, and reproducible outcome data.
Success requires useful answers without a worse incorrect-answer rate and a
measured improvement in the team's chosen latency or cost metric, including
fallback and allocated maintenance. There is no automatic adoption claim based
on reference examples, operator traffic, model interviews, or repository count.

Outreach or submission to another project is a separate explicit action.

Policy-coverage reports measure presence and policy acceptance. They do not
establish correctness or completed tasks; the independently scored workload and
external pilot supply those evidence levels.
