# F-05 source-only enrollment rule

This additional rule is fixed before F-05 candidate source inspection. It does
not amend the existing E1 selection or source freezes. Use only the `f05` queues
in `screening-reservations.json`, in their retained order, and the same historical
exclusions, fork/mirror checks and source-provenance requirements.

Enroll three distinct repositories per ecosystem, one task each. Visit candidates
in queue order for the following consecutive slots:

| Ecosystem | Slot 1 | Slot 2 | Slot 3 |
| --- | --- | --- | --- |
| Rust | repository / pre-clone | component / local checkout | repository / local checkout |
| Python | repository / pre-clone | component / local checkout | component / pre-clone |
| JavaScript/TypeScript | repository / pre-clone | component / local checkout | repository / local checkout |
| Go | repository / pre-clone | component / local checkout | component / pre-clone |

An eligible repository is public, active, non-fork code in the source-confirmed
ecosystem with build/test intent. Curated lists, source mirrors, tutorials lacking
a project test target and historical/development overlaps are source-based
exclusions. For a component slot, also require a named owned component and physical
path established by a package/workspace manifest or maintainer development
guidance; choose the lexically first such path with test intent. Record candidates
lacking that component as ineligible for that slot and continue forward. Once
screened, do not reuse an earlier candidate for a later slot. Quotas intentionally
sample different scopes and initial states, not population prevalence.

Pin the upstream commit at enrollment. A task asks for the repository-default
or named-component test outcome at that revision, with coverage and prerequisites
preserved. Source gold must distinguish supported alternatives, required abstention
and unresolved applicability. Missing documentation, unavailable setup, incomplete
tuples and later coverage misses are retained task limitations, never reasons for
post-enrollment replacement. Retain exact prerequisite/test-source bytes and
locators; do not infer unmentioned prerequisites or invent a one-package equivalent
of an aggregate workflow.

Prepare task requests without gold commands, prerequisite answers or scorer
artifacts. Independently review source gold and define a completion oracle and
error rubric before session execution. Actual environments, model configuration,
budgets, snapshot and enforced runtime isolation remain launch prerequisites;
source enrollment alone cannot satisfy them. No evaluated index, profile or
consumer output may influence source screening or task inclusion.
