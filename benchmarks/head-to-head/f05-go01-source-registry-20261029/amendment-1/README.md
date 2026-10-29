# Source registry receiver amendment 1 — source only

This append-only successor addresses F1 in the independent static review frozen at
`df6d752afd787928917416664c879a5422edf632750ba3e2d52cb37f2edce074`.
The original 33-artifact source proposal and the 11-artifact before-review remain
unchanged. No passed-review object is issued by the author; this successor awaits
independent static review and separate authorization before any owned Go commands.

`plan.json` and `subject.json` identify this successor. The three Go module/source
files, discovery sources, source selection, local input bytes, prospective helper
paths/environment/resources, output schema/version and oracle/collection gates are
unchanged. The runtime author has been asked to reuse the existing prospective
`/workspace/owned-bin/registry` and `/workspace/owned-go-{build,mod,path}` paths.
No runtime/executor is implemented here.

The amended common JSON loader refuses NaN, Infinity, -Infinity and numeric
exponents which overflow to nonfinite floats; encoding refuses nonfinite values.
The receiver requires diagnostic objects with exactly `code` and `message` plus
optional `sourcePath`. Code/message are nonempty strings; an included source path
must bind a selected file belonging to the reported package. Diagnostic text is
retained, not interpreted as outcome evidence. The receiver checks optional
`output` as a string and `emptyOutput`/`unordered` as literal booleans, including
false values. It also checks container objects before accessing their fields.
These checks establish schema consistency, not authenticity or semantic discovery
completeness. Diagnostic codes are nonempty strings; this change does not add a
new discovery-code policy or suppress unknown diagnostic messages.

Only the amendment copies of `build_input.py`, `read_registry.py` and
`crosscheck_registry.py` differ from their parents. Builder/root/discovery-data
references and comparator data references are adjusted solely for the deeper
subdirectory. Imports resolve the amended local loader/receiver; input provenance
and partial observations still come from the unchanged parent. `changes.diff`
shows the complete three-file delta. Copied original constructor and receiver
controls are byte-for-byte unchanged.

The 22 constructor and 26 receiver/comparator controls pass. The 38 amendment
controls replay all seven exact malformed before shapes and reject them, retain
valid source-derived/unresolved state behavior, accept all six producer-shaped
diagnostic variants and typed example fields, and reject additional malformed
keys/types/source paths and nonfinite numeric/encoding values. These are owned
synthetic Python data, never Go-produced corpus output. The common constructor
rebuilt the exact 21,446,036-byte input at SHA256
`0acd95252e7acfc23ce616d59125ebc98c0a7e4b079a789057e44a4479c88015`.
The temporary rebuilt input is outside the packet; original input bytes remain
unchanged. Ruff check/format passed with no cache. `verify.py` checks parent and
before-review artifacts, unchanged input/helper sources/context, and successor
subject hashes without writing. Its first local run assumed the reviewer artifact
map contained digest strings instead of objects; the retained local verifier-error
receipt records that corrected harness assumption, not an evidence-integrity failure.

All Go compilation, owned Go tests, helper execution and genuine partial-listing
crosschecks remain unrun. No Go, Node, daemon, network, package, native-task or
provider actions occurred for this amendment. The 61 failed native-listing packages
remain source-only and unvalidated live; dynamic children, TestMain behavior,
compile/type validity and complete native coverage remain unresolved. Native task,
oracle, campaign, execution-admission flags and current collection gate stay false
or unchanged. Author has extensive prior source/driver context; this is not a
fresh blind agent trial or consumer benefit evidence.
