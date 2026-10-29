# Operating readiness and declared F1 source audit — October 29, 2026

This packet retains actual GitHub observations and a bounded source audit. It
does not establish a seven-day operating window, execution of upstream projects,
or consumer benefit. No enablement settings were changed. The source-only freeze
preceded the separately authorized corrections retained under `f1-corrections/`.

## Operating observations

At the initial observation, both refresh and public-deployment workflows were
active; `INDEX_AUTOMATION_ENABLED` and `CLOUDFLARE_PUBLIC_DEPLOY_ENABLED` were
`true`. The optional adjudication-budget variables returned 404. Source resolves
the configured fallback to four calls when providers are available, otherwise
zero. No credential value was queried. Main protection required strict
`ci-gate` checks, enforced for administrators; Actions PR creation/approval was
enabled and the job requests its own write permissions.

The latest completed scheduled run, `40641402409`, succeeded on October 28. Its
actual batch artifact records 50 crawls/writes, zero failures and zero model
budget/calls/tokens. The artifact was uploaded before landing and contains no
landing or refresh publication receipt. The exact checker therefore returned
zero qualifying days with `receipt-unavailable`; its failing exit is retained in
`streak-before-0600.json`. A green run is not substituted for publication proof.

The October 29 scheduled first attempt was actually observed as run
[`40826758533`](https://github.com/maxwellsantoro/dotrepo/actions/runs/40826758533),
created at `06:01:46 UTC` on `eb43ab20ac0368c4926660ae060347305197f936`.
Timestamped run/job/artifact snapshots retain its observed progress. It completed
successfully and landed PR184 at `53ed7c41baab8d82b1b686143148a2e3c5e6f243`
after CI40828059561. The final receipt, however, says
`landed-deployment-disabled` with `publicationVerified=false`. The exact checker
returned zero qualifying days (`publication-not-verified`), retained in
`streak-after-40826758533.json`. No seven-day window or first qualifying day is
claimed. Its actual batch wrote 50 records with zero failures, calls or tokens;
all 34 retained telemetry controls passed.

Initial source inspection found no demonstrated enablement blocker. The actual
run subsequently exposed a publication flag-reading defect: both before/after
API observations show the public flag `true` with unchanged update time, but
the landing script converts any variables-API read exception into disabled.
`publication-boundary-finding.json` binds the source, exact receipt/logs, a
bounded offline exception counterexample and smallest proposed fix. The precise
actual API status was swallowed; a workflow-token Variables permission mismatch
is an inference, not an observed HTTP403. No settings were changed. At that
checkpoint no manual recovery had been run. The
receipt steps use `always()`; the final failure-restoration steps preserve failed
batch outcomes. Exact-base/source guards can refuse landing or publication if
main advances during the batch. The coordinator held unrelated merges until this
run completed, then advanced the working branch to the successfully tested landing.
No-change runs without publication receipts remain unqualified. Future provider,
network, budget or deployment failures are observations to retain, not presumed
successes. No initial checker patch was needed. After the actual run exposed the flag-read
boundary, the coordinator authorized the separate implementation retained in
`publication-fix/`. Its 71 focused controls passed, but it still requires a future
scheduled publication receipt. The existing checker controls
passed: `14 passed`; fixture controls are not operating-window evidence.

`current-record-freshness.json` reevaluates the existing local export from
`05:46:02 UTC`: 615 fresh, zero stale/unknown, oldest 24 days and no overdue
records. It passes the current-time age gate. This is local export evidence,
not a new live deployment or a new inspection of every source fact.

## F1 cohort and source findings

`f1-cohort-plan.json` declares the eight identities and three fields per identity
before upstream inspection. The risk sampler first excluded all historical and
reserved E1/F-05 identities plus the masked development diagnostic identities.
It sampled 20 of 423 eligible records with seed `20261029`, then selected the
first eight in risk order with at most two per language family. The protection
inputs, sampler and old record hashes are retained. Catalogue and educational
repositories remain in the denominator for an audit of justified abstention.

`f1-source-revisions.json`, `f1-source-catalog.json` and `sources/` retain exact
immutable upstream revisions, source bytes, Git blob identities, SHA-256 hashes
and URLs. GitHub connector base64 file responses were decoded without whitespace
normalization. Commit/directory observations use read-only GitHub API captures;
the connector's repository metadata is retained separately. No upstream code,
model or provider was executed. The source-freeze manifest binds the audit
subset separately from continuing operating observations.

`f1-source-assessments.json` contains all 24 field dispositions and source
excerpts. Five old fields are present and nineteen are absent:

| Disposition | Fields |
| --- | ---: |
| Existing supported documentation answer | 1 |
| Wrong repository scope | 1 |
| Potentially applicable command, insufficient support/context | 3 |
| Missing source-declared documentation answer | 3 |
| Correct scalar abstention in inspected sources | 10 |
| Correct documentation abstention in inspected sources | 3 |
| Unresolved | 3 |

The existing IBM root test scalar omits the separate `v2` and `gen/v2` modules.
Redigo's maintained test command requires Redis and includes `-race`; its bare
scalar loses that setup. Both Go build scalars lack a retained source-owned
repository-default build declaration. These findings do not claim that the
commands cannot run for a narrower or prepared task. The proposals withhold
unsupported bare scalars without inventing an aggregate replacement.

Missing documentation declarations are retained for xi-editor, IBM/fp-go and
rime-cloverpinyin. At the source-only freeze, the proposed URLs were exact source declarations
whose live availability, redirects and contents were unverified. Subsequent
bounded target observations are retained separately under `f1-corrections/`. xi-editor also retains
the conflicting older site-config URL. Qualified build/test observations preserve
their directory, platform and prerequisites; they are not successful executions.

After the freeze, the coordinator independently reviewed the source findings
and authorized four-identity writeback. `f1-corrections/` retains the guarded
before/after bytes, four scalar withdrawals, three exact docs additions,
Redigo docs reaffirmation and focused validation. All four original record
hashes matched before editing. Unrelated values, field assessments, generation
times, GitHub metadata and existing status/trust metadata were preserved in that
first correction. A subsequent coordinator review found that preserving the old
whole-record verification claim was inappropriate after a partial correction.
The append-only [`f1-trust-amendment/`](f1-trust-amendment/README.md) withdraws that
claim for xi-editor and rime-cloverpinyin, without changing record age or unrelated
facts. The first correction receipts remain unchanged; the amendment binds their
outputs to the final records.
Future scheduled refreshes may change these records, so integration must compare
current hashes and resolve same-identity conflicts explicitly. These inspected cases are known audit/development material, not a
fresh qualification set. The initial local report-generator locator error is
retained separately; it was corrected without changing upstream source bytes.
