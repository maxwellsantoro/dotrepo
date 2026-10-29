# Independent Go-01 oracle review — before amendment

Two bounded native-stream consistency findings remain in the frozen source-only oracle proposal. They do not represent an actual Go task outcome: every control used synthetic events, and `taskOutcomeObserved` stayed false. The author proposal remains unaccepted, its native collection placeholder remains empty, and no cache/native/provider execution was authorized.

The reviewed input is `f05-go01-oracle-preparation-20261029/freeze.json` SHA256 `d7b8b8f6ad1a5bf7616b05333fac739c32efd79ef40c4e696bf5c336d7074cf2`, binding sixteen files. Oracle SHA256 is `f58db90df7179c26413cdceb0efb9ddcb0a389902bae8a27524faea59a8c11dc`. All frozen files matched. The author’s sixty synthetic controls and complete existing-archive/span verifier independently passed into fresh outputs. `oracle.before.py.txt` retains the reviewed source; no author file was modified.

## Finding 1: terminal parents do not constrain descendants

At `oracle.py:253–268`, a nested run checks only that its immediate parent was previously in `ran`. Neither a terminal ancestor nor a parent terminal with outstanding children is rejected. Consequently both synthetic streams receive `candidateOutcomeObserved=true` and `testsPassed=true`:

- Parent run, parent pass, child run, child pass.
- Parent run, child run, parent pass, child pass.

The set equality at lines 269–270 eventually sees matching run/terminal identities but loses their lifecycle ordering. The existing missing-child-terminal negative control still rejects, so this is a hierarchy-state gap rather than a missing flat terminal check. The exact common-image Go testing source waits for subtests to finish before parent reporting; `toolchain-source-spans.json` binds that primary source to the already audited image inventory.

Recommended amendment: require live ancestors for descendant events/runs, and reject parent terminal states while any descendant remains outstanding. Match ancestry by exact slash-delimited identity and package, preserving parallel-sibling interleaving. Add positive parallel-tree controls and these two negative order controls.

## Finding 2: a failing child may have a passing parent

At `oracle.py:287–302`, package failure is compared with any failing test, but no equivalent child/ancestor consistency check exists. A synthetic failed child with its exact native `--- FAIL` diagnostic, passing parent, failing package and exit1 is accepted as a complete assertion outcome. Go testing's `common.Fail` recursively fails its parent; that source is retained in `toolchain-source-spans.json`. A passing or skipped parent cannot represent that failed descendant.

Recommended amendment: require every ancestor of a failed descendant to terminate fail, while allowing a parent’s independent assertion failure when its children pass. Do not reject a complete well-formed assertion failure solely because exit is nonzero. Preserve the existing runtime/resource/setup rejection and explicit distinction from completion.

## Source exclusion assessment

The exact 380 source exclusion candidates were checked against the already acquired archive. All raw source hashes and excerpts match. The 377 known-failing fourslash entries correspond exactly to the preceding independent proposal and have immediate unconditional skips. The additional bare fourslash skip is likewise immediate. TestReplay has an empty default replay flag and its source condition matches the unchanged no-replay wrapper proposal. The ATA literal subtest starts with its exact Todo skip. Its ASCII-space-to-underscore spelling is supported by `rewrite/isSpace` in the exact common-image Go source, and the literal occurs once in its source. These are candidate source exclusions, not policy acceptance or observed native identities/counts.

The original unknowns remain: dynamic compiler helper/configuration names, fuzz seeds, platform/capability and filesystem mappings, offline setup equivalence, complete native collection and accepted environment/policy bindings. No new patterns or capability assumptions were admitted. Missing embedded assets/Node/fixtures must not be silently reclassified as permissible skips.

The separate excluded-child-only stress case was initially marked as a possible acceptance gap in `challenge-results.initial.json`, then reconsidered against the task contract. A source-defined top-level wrapper can legitimately pass with a declared skipped child; parent pass alone does not imply every child body ran. The final challenge records this as an observed scope limit with no generic rejection expectation, rather than demanding every passing parent have an active child. Full dynamic-child coverage still needs the future source/collection/driver gates. The initial script/results are preserved, and no author evidence was rewritten.

## Other validated boundaries and limits

The actual unready policy and empty collection reject. Exact revision/archive/command/image/environment joins, timestamps, raw/digest bindings and the sixty existing negative/positive controls remain useful consistency checks. The current oracle asserts external receipts and acceptance; it does not authenticate them or prove that the claimed native collection is complete. No post-run successful artifact may supply missing pre-execution gold or collection facts.

`challenge-results.json` retains the three accepted malformed hierarchy/failure cases, a valid positive control, the missing-child-terminal negative control and the separately qualified scope stress case. All use `synthetic=True`; no actual outcome is claimed. The two finding fixes should be appended under a new author version and independently retested. This review is by the existing source/diagnostic assessor, not a fresh unfamiliar paid agent, and does not establish launch readiness or consumer benefit.

Only existing local archives, receipts and source were read. No Docker daemon, Go/npm/native task, package/source network request, model/provider, index/profile or E1 evaluation output was accessed. Review-local Python passed Ruff/check/format; archive/source/hash checks passed. The preparation packet stays frozen and unaccepted.
