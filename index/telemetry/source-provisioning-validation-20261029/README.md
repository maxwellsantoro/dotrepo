# Source provisioning integration checks — October 29

This packet retains integrated checks for the internal experiment runtime's
source-link support and hidden-answer alias amendment, alongside frozen source,
cache-preparation and CI-evidence packets. The base is main commit
`91643102c6083fda66827f68e43a06e7cdc8cec8`; `report.json` binds the runtime and test
inputs. These are apparatus/integrity checks, not agent-campaign observations.

The final Python suite passed 850 tests. The focused runtime and experiment
controls passed 175 tests. The complete release gate passed, including actual
exporter/consumer contracts, index freshness, Worker tests/smoke, release binary
smokes and VSIX packaging. The operator gate passed. Full remaining-eight source
integrity checks passed against the unchanged original enrollment and exact Git
trees. Release timings and command logs are retained here. Rust source and
dependency inputs are unchanged from the base's passing full CI; earlier local
Rust checks remain in the preceding validation packet. Final patch CI remains a
separate merge prerequisite.

The source-link-only baseline passed 846 Python tests. The new hidden-answer
regression fixture initially omitted valid frozen responses, causing four focused
and full-suite failures before the intended alias check. Those failures are
retained and do not demonstrate the alias defect. The corrected fixture passes.
The independent review owns the genuine before/after reproduction and its exact
runtime hashes; the original source-link review remains unchanged.

The prepared caches still have false audit/admission flags. A bounded independent
package/content audit does not establish offline restoration, task completion,
ignored-hook equivalence, exhaustive credential absence or all-twelve environment
qualification. Task-specific executable oracles and the campaign's model/settings,
budgets and final content-bound freeze remain open. No paid session or consumer
benefit result is claimed.

Ruff checks run on an isolated export of the selected Git index so concurrently
owned, unsubmitted work cannot change the reviewed input. The manifest binds
these reports; it does not turn retained assertions into independent execution.
