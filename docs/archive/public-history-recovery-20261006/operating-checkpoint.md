# Archive operating checkpoint — October 6, 2026

Source preparation is merged and validated. Cloud archive provisioning and
publication remain pending account setup. This receipt retains the failed
operating attempts rather than treating source CI or local reconstruction as
successful publication.

## Source and validation

[PR #140](https://github.com/maxwellsantoro/dotrepo/pull/140) merged as
`7ed2b68b56a9170bd4415e17c5e62bdc6a8015d1`. Final-head
[CI 37414446472](https://github.com/maxwellsantoro/dotrepo/actions/runs/37414446472)
passed on `a8bb68e7e3ffeba06925556b8f1638eb6536684e`; merged-main
[CI 37414776330](https://github.com/maxwellsantoro/dotrepo/actions/runs/37414776330)
also passed. Rust/index, Python, operator, release and the mandatory aggregate
all succeeded. Minimal and separate public-surface jobs were deliberately
unselected; the full release gate included public checks. Live branch protection
required strict `ci-gate` checks with administrator enforcement before merge.

Observed complete CI wall times, from GitHub's creation/update timestamps, were
177 seconds on the first PR head, 217 seconds on the final PR head, and 192
seconds on merged main. Inputs and cache conditions differ; these observations
do not establish a causal speedup or a guaranteed runtime.

Local validation passed the workspace gates, 612 Python tests, operator gate,
complete release packaging and final-index public checks. Original-exporter
recovery built ten locked, unchanged source revisions and reconstructed all
twelve frozen snapshots. Every identity, digest, log entry and manifest leaf
validated; all five retained byte anchors matched. All twelve manifest hashes
also matched the separately retained current-exporter diagnostic. The frozen
[plan and log](README.md) distinguish reconstruction from independently retained
historical bytes.

## Actual cloud result

The declared repository variable is now
`DOTREPO_PUBLIC_R2_ARCHIVE_BUCKET=dotrepo-public-snapshot-archive`.
[Deployment 37415031358](https://github.com/maxwellsantoro/dotrepo/actions/runs/37415031358)
failed during archive-history restoration. Cloudflare returned HTTP 403 and
code `10042`, with the instruction to enable R2 through its dashboard.
Publication was not reached.

[Recovery 37415120845](https://github.com/maxwellsantoro/dotrepo/actions/runs/37415120845)
ran on the same merged revision and failed at the read-only account-access
preflight with the same code. Historical exporter builds, reconstruction,
bucket provisioning and uploads were skipped. The preflight therefore avoided
expensive preparation on an account that could not serve the archive.
Neither failed workflow reset history or published a replacement snapshot.

Bounded live reads at `2026-10-06T04:46:32.459442+00:00` confirmed the current
snapshot remained
`a4e07e9651b9a1e0d6ce291b6648894f8adcbe97e5a4ddc79b1f5b01400c249b`.
The twelve-entry public history still equalled the frozen log. Its body SHA-256
was `0a1311ff2e78f2c9cff41f720da6f94e4030bbdebb338335c83a9147e17e7992`;
metadata SHA-256 was
`7ad4a635176051740575243c686a1b14f5a0b157617758e1e85a7e0798cd8e67`.

## Required continuation

The account owner must complete the R2 subscription setup in Cloudflare's
**Storage & databases → R2 → Overview**. Cloudflare's
[setup guide](https://developers.cloudflare.com/r2/get-started/) specifies an
account checkout flow; repository code and an API-token retry cannot substitute
for that setting. Bucket creation and object permissions remain unproven until
the account permits the actual recovery.

After setup, rerun the manual recovery on validated main, require complete
original-exporter validation and successful archive-log commit, then deploy
with the matching binding. Verify older snapshot manifests/inventories and
retained profile anchors, append-only history, current snapshot identity, and
private input refusal. A locally controlled checker exists for this purpose;
its controls are not live retrieval proof. Regenerate the bounded deterministic
refresh only after restore and publication operate. Historical packets remain
unchanged.

## Subsequent source integration

The audit remainder and verified 1.0.3 installation owners landed independently
in [PR #142](https://github.com/maxwellsantoro/dotrepo/pull/142), merged as
`b4dd5580416804f3c3ca46d56ff2eafd8fbac4dc`. Its source tree exactly matches
tested head `054ebff4de544e0006cd1c483ad7ad8f1e31357a`; final-head
[CI 37420064679](https://github.com/maxwellsantoro/dotrepo/actions/runs/37420064679)
passed all selected jobs and `ci-gate`. The merged-tree
[CI 37420688360](https://github.com/maxwellsantoro/dotrepo/actions/runs/37420688360)
is retained separately. The [1.0.3 delivery packet](../../../index/telemetry/stable-1.0.3-delivery-20261006/README.md)
binds its immutable assets, six crates, registry recovery and actual installation
controls. Source integration does not establish hosted publication.

The coordinator observed `CLOUDFLARE_PUBLIC_DEPLOY_ENABLED=true`, set it to
`false`, and verified that setting before landing source. This reversible
trigger change avoids repeated known-failing publication attempts while the
account setup requirement remains. It does not bypass restoration or archive
checks, change the archive bucket, reset history, or disable source validation.
Restore deployment enablement after R2 account setup and before dispatching the
recovery workflow, which requires that enablement. Then complete the recovery,
publication and live checks listed above. Automatic source-CI completion while
enablement is false must leave publication jobs skipped; a skipped workflow is
not successful publication evidence.
