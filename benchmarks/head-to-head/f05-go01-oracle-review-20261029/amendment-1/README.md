# Independent Go-01 oracle amendment retest

No remaining finding was reproduced within the two reported hierarchy issues and the bounded amendment controls. The exact three before-review malformed traces now reject, while valid sequential/parallel sibling trees, prefix lookalikes and complete deep assertion failures remain eligible synthetic candidate outcomes. Every result still has actual `taskOutcomeObserved=false`.

The reviewed author amendment freeze is `f05-go01-oracle-preparation-20261029/amendment-1/freeze.json` SHA256 `490e3d6e535b7d06e97ee500063a3baa55bd8f28fdee8abbf4b0d0f1137a7d1b`. Oracle SHA256 is `059ac111da3e00605b06e8afcea92467bc294b7cec05d35203bfd402fccaa726`. All ten amendment artifacts, all sixteen original author artifacts, and all ten artifacts bound by the independent before-review freeze were checked and match. `input-integrity.json` records those checks. The revision/archive/command/package-prefix/binding-key/exclusion-set constants are unchanged.

## Corrected behavior

The successor requires slash-delimited ancestors to be live when a descendant starts. It tracks unfinished descendants for each package/ancestor identity, preventing a parent terminal event while a child or deeper descendant remains outstanding. Failed descendant state propagates to ancestors, and failed tests are also checked against all ancestor terminal states. Prefix lookalikes remain separate identities. The original package, diagnostic, process, timestamp, source and coverage gates remain in place.

`independent-results.json` directly replays all three exact frozen before traces against both oracle versions: old acceptance and new rejection are preserved. Seven additional independent controls cover parallel prefix siblings with nested work; parent-only assertion failure with passing children; deep failure with a passing prefix sibling; package interleaving; independent top-level prefixes; unfinished grandchildren; and a failed grandchild with a passing grandparent. All ten controls passed their expected dispositions. Complete assertion failure remains distinct from noncompletion and returns `testsPassed=false` in positive failure controls.

The author's sixty base controls were rerun against the amended module into a fresh output. All eighteen author hierarchy controls were separately rerun after directing only their output directory to owned scratch and copying the immutable BEFORE binding as input. No author source or retained output was changed. These overlap with some independent regressions; the counts are separate runs, not a claim of eighty-eight unique cases.

An initial review-harness attempt assigned into the factory's tuple and raised TypeError before evaluating a case. The harness was corrected to mutate its contained event list; this was not an oracle failure. The final script is retained, passed Ruff/check/format, and produced the successful result artifact.

## Preserved limitations

The policy remains unaccepted with the same exact 380 proposed source exclusions, and the native collection placeholder remains missing. This amendment establishes no native test/package counts, cache/environment qualification, external acceptance or observed task outcome. Dynamic compiler helper/configuration/seed identities, capability/filesystem mapping, normal offline setup and ignored-hook equivalence remain unresolved.

The slash-delimited hierarchy contract is unchanged. Literal-slash naming ambiguity and unseen dynamic children still require the future native manifest/hierarchy adjudication; this review does not claim the scorer reconstructs arbitrary Go parent relationships. No generic active-child requirement was added. A passing source wrapper with a declared skipped child remains a manifest/coverage limit rather than automatically becoming malformed. Unknown skips at every depth remain rejected by the original source allowlist policy.

Only existing local source, immutable evidence and synthetic Python controls were used. No Cargo, Go/npm/native task, Docker daemon, network/package fetch, provider/model call, index/profile access or E1 evaluation output occurred. The reviewer has the prior source/diagnostic context and is not a fresh unfamiliar paid agent. The original before-review freeze remains unchanged; this appendix closes only the reported bounded scorer findings and makes no launch-readiness or consumer-benefit claim.
