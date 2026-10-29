# Collection driver amendment 3: selected test-only source

This append-only successor admits legitimate test-only Go packages. The parser's
final nonempty check now uses the already validated union of GoFiles, CgoFiles,
TestGoFiles and XTestGoFiles. It retains all existing filename, uniqueness,
cross-field duplication, source-inventory membership, module/directory and error
checks. Empty and ignored-only packages remain refused; IgnoredGoFiles does not
contribute selected source. This does not implement a general Go metadata/type
validator or change the intended package set.

The retained exact image tool source supports the rule independently of the
single result. `go/build/build.go:1079–1080` returns NoGoError only when the sum of
all four selected-file lists is zero. `alldocs.go:879–894` defines those fields
separately from ignored source. `internal/test/test.go:1144` distinguishes the
no-test path using both test-file lists. Raw source files and four exact spans
are bound to the frozen image inventory in `test-only-source-semantics.json`.

The actual failed attempt's raw go-list response and receipt are retained
unchanged. The command exited zero with 104 JSON package objects, 731,292 stdout
bytes, SHA256
`b4ef7caa0fafcffea826f91d0123143b6ed83e8f01f060e339975675d4597db8`.
The required internal/fourslash/tests package has no GoFiles/CgoFiles, three
TestGoFiles and 4,368 XTestGoFiles. All 4,371 selected test files belong to the
frozen source inventory; exact internal/external package declarations are bound.
The parent parser rejects that fixture; this successor accepts all 104 objects
without omission or filtering and validates every selected source membership.

The historical attempt remains incomplete at go-list: 16 daemon calls,
17.912 seconds, cleaned and absent, with no go-test-list collection. A corrected
offline parser does not turn it into a completed collection. Earlier failures,
parent author packets and reviews remain unchanged. No fresh daemon, Go or Node
call ran for this amendment.

The runtime delta is the final selected-source check plus the new packet identity
and explicit closure for source/raw-query fixtures and fake controls. The three
`.diff` files show it. Commands, source/image/Go-only cache, environment and query
expectations, resources, sandbox policy, stop conditions, tool/tree observations
and cleanup remain unchanged. The GOENV input/query distinction stays intact.
No package filter, omission, task substitution or resource increase is added.

Identity is `go01-collection-driver-amendment-3`; plan SHA256 is
`847c5e161f75f7d141f5dd59bc0df670d7261f1fad687184cafa4c1a64407000`.
The exact current plan/author-freeze subject must receive a fresh independent
passed review and coordinator scope/one-attempt authorization. Parent reviews
cannot authorize this subject. The template remains not authorized, with no real
acceptance or authorization created by this packet.

The 59 inherited fake driver, 40 admission-amendment, 22 GOENV, two fake transport
and 20 new test-only controls pass. Positives include genuine 104-object bytes,
internal-only, external-only and mixed test source, and a fully fake driver with
the required test-only package. Negatives include the parent regression, empty/
ignored-only selections, traversal/absolute paths, missing source membership,
cross-field duplicates, null fields, package errors/incompleteness and wrong
module/directory. These are source/metadata and fake controls, not new native
collection. Existing Node observer evidence is reused for unchanged inputs only;
Node was not run. Ruff check and format check pass with `--no-cache`.

`checks.json` binds the unchanged historical packets and current closure. Generated
Python caches are not evidence and are excluded from the freeze. Native task,
campaign and global-cache admission remain false; cost is unknown/null. Independent
review remains required. No new upstream imports, package/native commands, network,
daemon, Go, Node or provider/model action occurred.

Do not rerun generators or exclusive-output controls in this frozen directory.
Independent replays use a separate copy without generated control JSON or Python
caches; synthetic author/review fixtures do not confer live execution authority.
