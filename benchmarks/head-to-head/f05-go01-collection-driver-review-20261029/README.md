# Independent Go-01 collection-driver implementation review

Exact author freeze: `b176a6c3dfff4965a53e601a05eccab03257f9b3cfe78b5846317d29b2302eaa`.
All 33 author artifacts were checked before and after review and remain unchanged.
The reviewer authored the earlier source-only proposal and Go-only projection,
but did not author this driver. This is independent implementation review with
that context disclosed, not a blind task trial.

The closure's 59 fake driver controls, two fake transport controls and six
coordinator-authorized synthetic Node builtin observer controls passed on an
isolated copy. Metadata verification passed. The copy omits only generated replay
outputs before execution; original frozen files were never rewritten. Retained
`replay-*.json` files bind the rerun observations, including host Node identity.

Three bounded amendments are required before a live decision:

1. **Acceptance is not bound to the current reviewed driver.** A new current-plan
   authorization accepts an old scoped acceptance and old review artifact even
   when both explicitly bind a different plan. `acceptance_reuse.py` reproduces
   the coordinator's concern with owned JSON only. Require exact current
   driver-plan/reviewed-packet identity in scoped acceptance before daemon.
2. **Actual inspect accepts conflicting or extra tmpfs configuration.** It accepts
   `size=8g,size=16g`, a later `suid`, or an extra tmpfs root. The actual create argv
   remains safe; no unsafe execution occurred. Tighten the successor collection
   wrapper to the exact intended tmpfs map/options, preserving the frozen helper.
3. **Package parsing accepts contradictory source identity metadata.** A required
   import path may point to another directory; `GoFiles=['..']` or duplicate
   selected filenames pass. Reject inconsistent module-relative directories and
   unsafe/duplicate selected source basenames; retain valid package cases.

`challenge-results.json` preserves all 23 independent cases: 17 matched intended
acceptance, six exposed the latter two findings. `acceptance-reuse.json` retains
the separate old-acceptance/new-plan case. `review.json` gives exact locators,
triggers, implications and minimal recommendations. Author/root must create an
append-only successor; this review edits no implementation or historical helper.

The review also inspected exact input/environment/resource boundaries, Go-only
projection, command closure, lossless raw outputs, source/tool observations,
cancellation/deadline, receipt retention and cleanup/absence. The prospective
explicit GCC/G++ context remains distinct from an observed Go environment.
Source trees are observed at two instants; modes and all intervening changes are
not proved. Arbitrary misleading initializer stdout is a disclosed listing limit,
not a successful task oracle. No test/campaign benefit is established.

Only fake transports and trusted local tooling ran. The sole real non-Python
control executed the already authorized Node builtin observer against isolated
synthetic filesystem data; no npm/project imports occurred. No daemon, Go, Cargo,
package, upstream native execution, provider/model or network action occurred.
This packet grants no execution or global/cache/native/task/campaign admission.

Reproduce the retained fake independent checks in a fresh copy of this review
packet (their result files use exclusive creation):

```sh
uv run --offline --no-sync python challenge.py
uv run --offline --no-sync python acceptance_reuse.py
```

Their bound author script-copy path remains recorded in `author-binding.json`.
Ruff check and format check passed with `--no-cache`. Original before evidence
and findings must remain append-only even after any successor fixes.
