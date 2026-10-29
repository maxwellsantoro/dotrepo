# Source screening before enrollment

This rule is fixed before candidate source inspection. `source-frame.json`
retains GitHub repository-search results from four language queries, with returned
rank and public repository identity. `screening-reservations.json` hashes that
frame and the historical/development identity exclusions. Neither capture queried
the evaluated index or consumer acceptance.

Within each query, remove excluded identities and duplicates in the fixed query
order Rust, Python, TypeScript, Go. Sort remaining identities by SHA-256 of
`dotrepo-applicability-20261029-source-screen-v1`, newline, lowercase identity;
break ties lexically. Reserve even zero-based positions for E1 qualification and
odd positions for F-05. Preserve case for source retrieval but normalize identity
comparison. Reservation is not eligibility or task enrollment. Screening may
identify further fork/mirror overlap; exclude those with a source-based reason.

For E1 qualification, traverse each reserved queue in order. Select the first
three eligible repositories per ecosystem, with two tasks per repository: the
repository-default test task and a named component test task. Eligibility requires
maintainer-controlled source for a public active code repository in that ecosystem
and an identifiable owned component with a physical path and test intent.
Confirm ecosystem from source, not query membership alone. Choose the lexically
first component path established by the root workspace/package manifest or
maintainer contributor documentation. Record every screened identity, revision,
source, decision and exclusion reason. Do not skip a repository because its
instructions are incomplete, setup is unavailable, or dotrepo may lack coverage.
These become missing/unresolved gold or task limitations, kept in the denominator.
Stop at three enrolled repositories per ecosystem or exhausted reservations.

Freeze the upstream revision at enrollment. Inspect root manifests, README and
contributor/test guidance, the selected component's manifest/guidance, and any
explicitly referenced prerequisite sources needed to assess the tuple. Retain
source bytes with URLs, locators and digests. Gold alternatives require evidence
for command, directory, repository/component coverage and prerequisites together;
record required abstention or unresolved evidence instead of guessing. Source
assertions do not establish actual execution success. No upstream build/test code
is executed during screening.

For F-05, preserve its reserved queues while defining a task-class screening rule
before source inspection or enrollment. The experiment's marginal scope and
pre-clone/local quotas still apply. Its source roster and environment/oracle work
remain pending; these reservations do not satisfy the launch freeze.

Search results favor prominent repositories and may include tutorial or list
repositories; source-based screening must record such exclusions. This bounded
source frame is not representative population sampling. Historic exposure
exclusions do not establish that a model has never encountered the source.
