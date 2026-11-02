# Experimental repository discovery

RepoDigest's local MCP service returns compact repository profiles through
`repodigest.find`. Agents can compare candidates in one response, then use
`repodigest.describe` for full profile evidence and `source.read` for selected
source passages. Serving uses SQLite and admitted records; it performs no model
call, network request, source replay or repository execution.

For metadata-first discovery followed by explicit source assessment checks, see
[experimental requirement assessments](experimental-repodigest-requirements.md).

This extends the existing experimental service. It does not introduce a public
protocol version or change the public instruction consumer. The existing
`repositories[].repository` key remains; find results now include profile fields
and match evidence. Consumers depending on exact old response equality must adapt.

## What profiles establish

Profiles bind repository, revision, tree, acquisition time, compiler policy and
source hashes. They contain explicit manifest descriptions, keywords, ecosystem
signals, runtime declarations and dependency-field counts, plus up to four
literal root README passages. Sources are untrusted publisher data. A retained
description establishes what the source says; it does not independently establish
that the advertised capability works. Git content identities do not authenticate
a maintainer's endorsement of this independently compiled index.

Full profiles retain source paths, body hashes and field selectors or line
ranges. Compact results retain their profile digest, revision, a 160-character
purpose passage, ecosystem languages, up to two labeled interfaces and matching
source paths. Constraints, dependency counts, literal evidence passages and full
coverage remain in `describe`; shared limitations appear once per response.
Truncated purposes are marked. In the full profile, `checkedAt` is retained
source acquisition time, not a guarantee that the revision is today's HEAD.
Maintenance status, offline operation, tested runtime compatibility, complete
capabilities and resolved dependency footprint remain explicit unknowns.

The compiler handles inspected `package.json`, `pyproject.toml`, `Cargo.toml`
and `go.mod` files. Language filters mean **manifest ecosystem**, including
development/tooling components, rather than predominant implementation language.
CLI/library filters recognize explicit manifest declarations, such as `bin`,
`exports`, `project.scripts` or `[lib]`, labeled `declared`.
They also recognize a `derived` Cargo library when both the manifest and its
conventional `src/lib.rs` body have been inspected. Evidence
binds both file hashes and the documented [Cargo target-discovery rule](https://doc.rust-lang.org/cargo/reference/cargo-targets.html#target-auto-discovery).
The rule honors disabled auto-discovery and the 2015 edition's different defaults.
Cargo `[[bin]]` declarations and inspected conventional `src/main.rs` files
establish only a binary target in full-profile `targetEvidence`. They do not
establish a CLI interface: the executable may be a GUI or server. Unresolved
workspace editions, uninspected target bodies and unsupported layouts remain
unknown. A derived target does not establish compilation, useful public
API coverage, feature/platform compatibility or execution success. Python
packaging alone and Go module metadata alone still do not classify an interface.
An unknown interface can be excluded by a strict filter; omission is not proof
of absence.

Dependency counts describe only the named declaration field. Missing or dynamic
fields are unknown, distinct from an explicitly empty list/table. Conditional,
optional, feature-selected, workspace, development, build and transitive effects
are not resolved. A count is not installed size or a portability result.

## Agent calls

```json
{"query":"configuration parser", "language":"Python", "limit":10}
```

```json
{"query":"image conversion", "language":"Rust", "kind":"cli", "limit":10}
```

Use these arguments with `repodigest.find`. Optional `interface` accepts
`command-line` or `library`; `kind` accepts `cli` or `library`. Language accepts
`Python`, `Rust`, `Go` or `JavaScript`. All structured filters must match one
manifest/component declaration, so a Python component cannot borrow a JavaScript
component's CLI declaration. An empty query with filters can browse that subset.

Search uses literal prefix terms with OR semantics and SQLite FTS5 BM25 ranking.
When a language filter is provided, its exact language word is removed from
the text terms so the filter alone does not create a lexical match.
It searches descriptions, declared keywords, manifest signals and bounded README
passages. There is no semantic reranker. Results explain textual matches, preserve
unmatched query terms and expose uncertainty. A mention of “offline” in a negative
sentence remains a text match with its source passage; it never becomes an
offline-support fact. Identity and manifest-signal matches are identified separately.
Queries preserve Unicode words. Match explanations normalize case, accents and
separators for common prefix matches; these explanations are not a second
integrity check and can differ from SQLite's tokenizer on unusual characters.

Queries are limited to 200 characters and the first 16 distinct non-stopword
terms. Up to 20 profiles are requested per call, with a combined 32 KiB JSON
budget. The response may contain fewer profiles to meet that budget and sets
`moreCandidates`. It is a shortlist, not an exhaustive catalog. The reader
examines at most 100 candidate records and stops once it has enough results;
it does not materialize every matching profile in memory. Invalid or obsolete
profiles refuse visibly rather than falling back to fetching or model synthesis.

`repodigest.describe` returns the selected repository's full profile alongside
its existing component inventory. Each compiled profile is at most 32 KiB,
contains at most 16 inspected manifests and records omitted/unreadable manifests.
README extraction is limited to the first 150 lines and four short passages.
Coverage is always partial; search recall and interpretation quality need separate
evaluation. No result grants execution permission.

## Admission and refresh

Use the existing `repodigest_store.py ingest` command and service invocation
described in [retained source serving](experimental-repodigest-source-cache.md).
Re-admit trusted snapshots under the new compiler into a new database or an
operator-managed current store. Historical benchmark databases remain frozen.

Admission compiles profiles once from already verified source bytes. Immutable
profile objects are referenced by the compiled records and admission receipt.
Current search rows and indexed facets update in the same transaction as current
repository records; historical objects remain. Source changes, changed inspected
coverage or compiler-policy changes require re-admission. Older databases without
discovery profiles return an explicit re-admission requirement. Unchanged
admission verifies the immutable profile and its receipt binding, then restores
the derived search rows and facets. Corrupt immutable profiles fail closed.

The historical retained-source demonstration and Discovery-100 cohort preparation
remain on the preserved experimental branch, with
[compact result documents and provenance](research-evidence-20261030/README.md)
in this scoped source delivery. Their engineering checks do not establish agent
savings or net economics. A competent GitHub search and
selective-inspection baseline, candidate quality and missed relevant projects
must be evaluated alongside acquisition, refresh and total operating effort.

The completed [fixed-corpus comparison](experimental-repodigest-discovery-comparison.md)
used an offline metadata-search baseline over the same 100 candidates. It is a
metadata baseline, with no claim to measure live GitHub search.
