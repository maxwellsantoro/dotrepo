# Generic agent integration pilot

This package is ready for an external team to integrate. No participating team or
independent adoption is claimed. A deployment by the dotrepo operator remains
operator evidence even when it uses this package.

## Deliverables

- Dependency-free HTTP client: `examples/external-consumer/lookup_before_scrape.py`.
- MCP equivalent and setup: `docs/external-consumer-integration.md`.
- Executable fallback experiment: `lookup-first` arm in `benchmarks/head-to-head`.
- Structured outcome template: `examples/external-consumer/pilot-report.example.json`.

## Integration contract

1. Normalize the repository identity and select the fields the task needs.
2. Fetch its profile with a bounded timeout.
3. Check the returned identity, conflicts, record age, requested fields, and any
   field-specific unresolved assessments. Inferred build/test commands require
   source fallback. A 200 response is not task success.
4. On rejection, inspect upstream sources. Retain both the fallback reason and
   source evidence; never execute a returned command merely because it is present.
5. Record the final task outcome, not just whether a lookup was served.

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

## Positive command acceptance

The reference consumer accepts a requested primary build/test command only when
it is a nonempty string with an explicit `present`, `extracted`, high-confidence
field assessment, a nonempty source, and a check timestamp matching the record.
Missing, invalidated, malformed, unspecified, inferred, or weaker assessments
require upstream fallback. Record-wide confidence and maintainer status do not
substitute for this contract; no maintainer-authority exemption is implemented.
Unsupported response versions and non-string requested values also require
fallback. Acceptance is metadata suitability, not permission to execute a command.
The benchmark leaves field confidence unknown when absent.

Policy coverage is published on the efficiency page and in its linked JSON.
It distinguishes value presence, policy acceptance, independently established
correctness, and completed tasks. The last two remain unmeasured in the coverage
report; they require the existing benchmark and independent pilot evidence.
