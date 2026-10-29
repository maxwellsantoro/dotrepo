# Go-01 source registry experiment: source proposal, Go unrun

This is a bounded source-only implementation proposal for the unchanged frozen
Microsoft TypeScript task/revision. It does not replace the current native
collection gate or qualify an oracle, environment, native task or campaign.
Go compilation, Go tests and helper execution have **not run**. Independent
static review and separate root authorization are required before any Go command.

`registry.go` is one stdlib-only helper. It reads a closed JSON object on stdin;
the selected Go file bytes are supplied directly to `parser.ParseFile`. It never
opens those paths, resolves/imports upstream packages, type-checks, generates code,
executes source bodies, launches processes or uses the network. The only CLI
streams are stdin, bounded stdout and errors on stderr. `go.mod` declares no
dependencies. The prospective module build copies only go.mod, registry.go and
registry_test.go; retained evidence and input data stay outside that module.

## Exact discovery boundary

The two retained image source files are bound in
`discovery-source-bindings.json`. Go's load/test.go:628–643 consumes the selected
TestGoFiles then XTestGoFiles; 587–622 defines syntactic signatures and Unicode
prefix names; 732–817 supplies declaration, TestMain and example discovery.
go/doc/example.go:50–150 and 595–609 defines example/output-comment semantics.
Original source bytes and BSD license are retained. Mirrored helper predicates
carry the Go authors' attribution; see GO-LICENSE.

The helper preserves internal/external source order, uses the exact prefix rule
(the following rune must not be Unicode lowercase), excludes receiver methods,
and mirrors the syntactic pointer-name signature rules. It distinguishes wrapper
TestMain(*M) from ordinary TestMain(*T), including the frozen special branch's
signature-check behavior. The syntactic checker deliberately does not resolve
whether a qualifier denotes package testing. Generics and other signatures follow
the source's checks; none of this establishes typed/compiled validity.

Examples use `go/doc.Examples(file)`, source Order and output/empty-output rules,
not documentation symbol-association filtering. All declarations have stable IDs,
kind/name, exact source path/hash, role and physical positions; `//line` directives
cannot rewrite those physical locators. Duplicate runtime names retain separate
IDs and yield unresolved diagnostics, as do multiple TestMain wrappers, parse or
package-clause problems. No declaration is silently set-deduplicated. Every
package and the root keep compile validity explicitly unestablished.

Dynamic children, fuzz seed arguments, conditional branches, runtime skips and
capabilities, and whether TestMain actually runs the tests remain unresolved.
This output is a source registry, never a report of tests or native collection.

## Bound constructor and input

`build_input.py` uses Python's standard library only. It pins the exact existing
driver/result freezes, 104-package inventory, source archive/inventory and original
selection-context hashes. It verifies package/module/cwd identities, selected
literal unique names and source membership, then reads selected regular tar member
bytes without host extraction. Hashing the full tar before/after binds the other
members; selected byte hashes are independently checked. Ignored files never
enter the selected data.

The closed corpus has 4,589 selected files and 15,262,944 source bytes; the largest
file is 4,029,319 bytes. `local-input.json` is 21,446,036 bytes with SHA256
`0acd95252e7acfc23ce616d59125ebc98c0a7e4b079a789057e44a4479c88015`.
It is gitignored local data, reconstructible from the frozen constructor and
already retained archive, and bound by `input-provenance.json`/the packet freeze.
The committed provenance retains every selected path/hash/size, not all source
bodies. The Go decoder also pins the ordered selection digest, package count,
selected file count/bytes, source context and every embedded file digest.

Bounds are 32MiB input, 24MiB selected source, 8MiB/file and 6,000 selected files.
Full source scanning is capped at 512MiB transport, 256MiB expanded and 70,000
members; the exact archive has 68,062 members. Two initial preparation refusals
are retained: an undersized 20,000-member bound and refusal of legitimate
whitespace-named unselected baseline fixtures. They were constructor assumptions,
not upstream defects. The corrected archive view accepts those physical data
paths without extraction or including them in the selected Go input. Source and
selection bytes were not changed.

## Output and future receiver

The proposed CLI emits one deterministic gzip member containing compact JSON with
sorted object keys, ordered arrays, integer-preserving numbers, default Go JSON
escaping and final LF. It marshals, sizes and compresses before writing anything.
Header fields have no clock, filenames, comments or randomness. Caps are 10,000
declarations, 8MiB expanded and 2MiB compressed; actual stdout/stderr still share
the existing combined command limit. No binary output is decoded as UTF8 or
printed. Future transport retains exact rawstdout.bin bytes.

`read_registry.py` bounds decompression with max+1, checks CRC/eof, exact header,
single-member/no trailing bytes, unique JSON keys, source/helper contexts,
package/role/file membership, physical bounds, stable unique IDs and counts.
It cannot authenticate a helper execution or source semantic correctness merely
from consistent JSON. Actual raw command/tool receipts remain a separate gate.

`partial-listing-observations.json` preserves only observations from the failed
native listing. `crosscheck_registry.py` is prepared but unrun against Go output.
It will compare the ordered declared names to 25 successful partial-listing
packages and empty source registries to 18 no-test diagnostics. All 61 failed
packages remain source-only, unvalidated live (40 have test sources and 21 do not).
Printed name lines alone do not authenticate an observer. No full native manifest
is inferred from this comparison, even if it later matches.

## Checks and separate tool context

The 22 Python constructor and 26 Python receiver/comparator controls pass. They
exercise source membership, ignored/missing/changed files, archive paths, input
keys, gzip caps/CRC/truncation/member ambiguity, schema/ID/context defects and
synthetic partial-comparison omissions. Their Go-like source fixtures are data.
Ruff check and format check passed with --no-cache. Earlier control receipts are
retained. The Go unit fixtures are **written but unrun**; they include Unicode,
bare names, methods/signatures/generics, TestMain variants, duplicates, examples,
line directives, parse failures, JSON ambiguity and deterministic gzip encoding.
An explicitly authorized host gofmt pass formatted and syntax-parsed only the two
owned Go files; its path/hash and limits are retained in
`host-gofmt-receipt.json`. It establishes no target-Go1.27 library equivalence,
compilation or test validity.

`plan.json` separates target selection context (original CGO1/GOWORK repository)
from future owned-helper build context (CGO0/GOWORKoff, no dependency/network
access and empty owned caches). Its fixed future unit command is
`go test -json -count=1 -timeout=60s .`, nonrecursive in the owned module. Proposed
build and CLI interfaces use the same audited image, 3CPUs/4GiB/256PIDs and
900s+60s bounds; root will reuse its existing isolation boundary. These strings
are a plan, not execution authorization. No new executor is implemented.

This author knows the development/source/partial-result history; this is not a
fresh blind model/corpus exposure. Apart from the owned-source host formatting
pass, no Go compiler/test/helper, Node, daemon, package, upstream import, native
task, network, provider or model action ran. No qualification, gate removal
or consumer benefit is claimed. Preserve all original failures, gold and oracles.
