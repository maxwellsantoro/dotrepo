# Compose source-completeness next disposition

The chosen known-development task remains `make test` from the repository root at
`docker/compose@343bb382d2192b88d84af49971bb5cb99bee268c`, for the maintained
main-module unit default under the documented Linux conditions. The plan was
written before this packet's additional source reading. No narrower task replaces it.

The exact command, root relay and documented prerequisite chain are supported.
BUILDING calls this all unit tests; Make invokes Buildx Bake test; Bake selects
Dockerfile test-coverage; the inherited test stage declares tool/native/module
setup and the exact test command. This documented applicability does not require
independent successful execution or universal proof of dependency correctness.

The single remaining question stays unresolved: does the untagged package list
select the intended complete unit package set when execution uses `e2e` build tags?
The literal `$(TAGS)` inside Dockerfile RUN is shell syntax, not a Make expansion.
This packet does not invent its output, treat it as a flag, declare it fatal, or
add a prerequisite executable named TAGS. The literal e2e substring filter also
needs a membership account before it can establish an exact exclusion boundary.

Nine already-retained inert files totaling 33,902 bytes were inspected and copied
byte-exactly, within the 12-file/1MiB limit. Their hashes and Git blob identities
match original retained evidence. The complete frozen root Git tree reconstructs
to its bound SHA but contains only 27 top-level entries; it does not contain
recursive pkg/internal/cmd bodies or selected-file/build-constraint membership.
The bounded locator follow-up found no already-retained full archive or recursive
inventory within the owning packet locations. No new acquisition occurred.

Three abstract package-set controls show both a consistent selection and possible
omissions from tag-only packages or a literal e2e substring in an unrelated package
name. They are owned data examples, not actual Compose packages or native Go results.
The retained representative unit test is evidence of test intent, not exhaustive
membership. The needed next fact is that concrete selection relation, not inspection
of every dependency or helper and not a green baseline. Until then, a complete-tuple
claim abstains while the source-supported documented default remains visible.

`uv run python -B controls.py` checks hashes, Git blob identities, source spans,
the one-level root tree and abstract examples; its output is exclusive creation,
so replay in an owned review copy or remove only the replay copy's controls.json.
Ruff check/format passed. The assessor has prior Keras/Compose/E1 familiarity;
this is known development evidence, not fresh blinded qualification or consumer
benefit. No sources were imported/executed, no network/install/daemon/provider
activity occurred, and no shared record, source packet or implementation changed.
