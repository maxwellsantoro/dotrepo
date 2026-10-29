# Independent static source-registry review: one receiver finding

Author subject: source-registry FREEZE
`b2fd2550fd9ca1b5dc20774badfb77863e28236cc0535f11c6012a5aa6a0ab8d`,
plan `49637b49865d50faf365833ea4d6ea986bf6dffd7de0a33687d9687db752d5c0`.
All 33 original artifacts and the bound ignored input remain unchanged.
**No passed-review object is issued for this base.**

The bounded Go design is consistent with the intended source-only experiment:
stdlib imports, stdin-supplied bytes passed directly to parser.ParseFile, no opened
project paths/importer/typechecker/process/network/generation, and stdout prepared
under size caps before emission. The mirrored name/signature/TestMain predicates
and go/doc example handling match retained Go discovery source. Physical locations
ignore line-directive remapping; duplicate or invalid discovery retains diagnostics.
These are static observations, not compilation or execution proof.

The exact 21,446,036-byte input was independently reconstructed to SHA256
`0acd95252e7acfc23ce616d59125ebc98c0a7e4b079a789057e44a4479c88015`:
104 packages, 4,589 selected files and 15,262,944 source bytes. Every embedded byte
payload matches its hash/size. The two discovery source files match the frozen
image inventory. Target selection context stays separate from prospective owned
helper build context; no collection/oracle gate is changed.

## F1: receiver accepts malformed schema and non-JSON values

`receiver_challenge.py` retains ten synthetic Python cases. Valid source-derived
and unresolved outputs accept; a state hiding diagnostics rejects. Seven malformed
cases unexpectedly accept:

- Scalar, empty-object or wrongly typed diagnostic entries.
- `output=[]`, `emptyOutput=1`, or `unordered="yes"` on a declaration.
- Non-JSON `NaN` accepted by the common JSON loader and then an optional field.

The typed Go producer would not normally emit these shapes. No bad actual helper
output is asserted: the helper has not run. Nevertheless a receiver claiming a
fully validated observation must reject them. The append-only fix should enforce
diagnostic keys/types, optional declaration string/bool types, and strict JSON
nonfinite rejection while preserving valid unresolved output. Preserve the frozen
base and these before cases; do not silently relax or rewrite them.

## Checks and remaining gates

Copied Python controls pass: 22 constructor and 26 receiver/comparator cases.
Four additional Python state/comparison checks confirm that diagnostics survive
partial pass/skip/fail comparisons and all 61 failed packages remain unvalidated.
The raw source-registry output must retain full diagnostic payloads even when the
comparison summary lists diagnostic package names. A valid exit-1 unresolved
observation is distinct from semantic correctness and never qualifies a task.
Ruff check/format pass with no cache.

Static gzip inspection agrees on deterministic header, 2MiB compressed/8MiB
expanded limits and bounded single-member CRC/eof/trailing-data rejection. Actual
Go encoding, compilation, owned unit fixtures, CLI and genuine source/native
crosscheck remain unrun. Author's expressly allowed host gofmt Go1.27.1 provided
format/syntax evidence only, not target Go1.27.3 qualification.

Reviewer authored earlier source/projection proposals and driver/result reviews,
but not this implementation; this is not a blind task trial. Only trusted local
Python data/hash/source and synthetic controls ran. No Go, Node, daemon, upstream
native execution, network, package or provider action occurred. Separate amendment
review, runtime review and root authorization remain required before owned Go
execution. All execution, task/native, campaign and oracle admission stays false.
