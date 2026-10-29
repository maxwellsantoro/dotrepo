# Go01 source-oracle implementation — independent preparation review

The frozen amendment passes this bounded implementation review with no findings.
It provides source-expectation derivation and synthetic scorer preparation only.
Actual evaluation remains unconditionally blocked by the missing reviewed capture
join; this review admits no actual oracle, task, campaign or runtime action.

All 15 author artifacts are unchanged. Pure derivation and the verifier reproduced
the complete 104-package, 5,972-name map at SHA256
`768482aa2dcec46151e529a1126a8d74fbaba56f168d86c915002aa70d869e4a`.
Benchmarks (48) and TestMain wrappers (11) are excluded from required case events. The
40 empty-name packages, 39 packages without selected test source, and 18 previously
observed no-test diagnostics remain distinct. Every package still needs coverage.

The complete retained diff and original helper/constant ASTs were checked. Skip
policy, assertion/process checks and lifecycle semantics are retained. The sole
lifecycle change narrows acceptance: source-empty binder has selected test source,
so it cannot claim a `[no test files]` package skip. No skip exclusions are added.
Normal full Hereby command/setup, effective selection and all-depth runtime event
requirements remain mandatory. Dynamic children are checked when observed; no
new exhaustive enumeration requirement is invented.

The author’s 44 synthetic/data controls and verifier passed. Twenty-five independent
controls passed, including full pass/assertion-failure positives, retained malformed
hierarchy cases, parallel/prefix-distinct siblings, deep failure propagation,
missing/unknown identities and packages, tampered maps/context, false no-test skip
and forged capture booleans. Actual-mode evaluation always refuses; all synthetic
actual-outcome/admission flags stay false. Ruff passed with `--no-cache`.
`challenge.py` writes its result exclusively; replay into fresh outputs with original
AUTHOR/ROOT bindings. It imports only frozen trusted local Python/data functions.

A concrete existing-shell same-tool-call event export join still needs implementation,
limits and independent review, followed by actual setup/tool/selection and full C1
conditions. A hash, agent-writable event file or true JSON receipt flag does not supply
that join. No general runner, protocol, new cache, resource increase or native retry
is needed or authorized here. Current failed native results remain noncompletion.

The reviewer authored earlier oracle/source/decision/helper-result reviews but not
this amendment. This is independent implementation review with prior context, not a
blind task trial. No Go, Node, Docker, upstream/native, network or provider actions
ran. Current oracle, task, campaign and execution admissions remain false.
