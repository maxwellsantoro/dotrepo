# Bounded repository selection

This local experimental flow finishes with preliminary source-supported choices
or an explicit `none-established`. It builds on the existing source assessment
reader; it does not interpret natural language requirements or execute projects.
Use it from a source checkout, not the published `dotrepo-mcp` binary.

Start the service as in [requirement assessments](experimental-repodigest-requirements.md),
with an admitted source store, `--allow-requirement-assessments`, and preferably
`--metadata-index` for cheap discovery. `--compiled-sources` enables original
source inspection; it does not authorize HTTP on misses unless separately configured.

## Complete a decision

1. Call `repodigest.shortlist` with `queries`, a list of 1–3 short search strings,
   and an optional `language`. It returns a `selectionId` and at most four
   distinct leads. Keep that ID for follow-up queries. The whole selection has
   three distinct search attempts; case/whitespace-equivalent repeats reuse the
   previous result. No page-size argument is necessary. Query ranks are combined
   round-robin so a later precise query can change the shortlist; this is an
   allocation rule, not a suitability ranking. Use the latest returned shortlist.
2. Match mandatory requirements to the returned component-specific assessment
   keys. `describe` indexes assessment-bearing components independently of its
   manifest-component page. If `requirementKnowledgeNextOffset` is non-null,
   continue with `requirementOffset`. It is distinct from component `offset`.
   `describe` accepts optional exact `revision`, including retained history;
   unavailable revisions do not borrow a current assessment.
3. Use `qualify` or exact-revision `source.list`/`source.read` for focused gaps.
   Natural-language requirements without an aligned key remain unmapped. A
   missing key or source passage is unknown, not false. Source fallback findings
   need their own attribution; a tool does not silently promote them.
4. Call `repodigest.decide` with the selection ID, 0–4 exact candidate targets,
   mapped `requirements`, and any `unmappedRequirements`. An empty candidate
   list can finish a search with no supported lead. Supported candidates meet
   every mapped condition and have no unmapped mandatory requirements.

For the existing MarkItDown development record, an example final call is:

```json
{
  "selectionId": "selection-1",
  "candidates": [{
    "repository": "github.com/microsoft/markitdown",
    "revision": "7482c092d9c0074a89803c9fdb63a969e7fe17fc",
    "component": "packages/markitdown"
  }],
  "requirements": [{"key": "conversion.docx-to-markdown", "expected": true}],
  "unmappedRequirements": ["Works without LibreOffice"]
}
```

That unresolved mandatory condition prevents a supported selection. Even a fully
supported result is preliminary: no ranking of the best project, runtime test,
current-HEAD check or execution permission follows. `none-established` means no
choice was established from these targets/evidence, not that no suitable project
exists. Stop exhausted catalog searches and report the exact remaining gap.

## Bounds, recovery and accounting

`find`, `describe` and `source.list` visibly cap oversized positive integer limits
at their advertised maxima. Invalid types, nonpositive limits and unsafe paths
still refuse. `limitAdjustment` reports a cap; pagination retains its meaning.

There are at most 16 selections in a server process. Each retains started/failed
searches, reused queries, omitted leads and whether it reached a decision.
`repodigest.selection_status` reports every attempt, including unfinished ones;
pass a selection ID to retrieve its state or immutable final decision. Export
the ledger before server exit. It is process-local workflow accounting, not a
durable user history, model-usage meter or correctness grader.

Shortlists and decisions are bounded to 32 KiB. An oversized decision refuses and
remains unfinished; narrow its candidate set explicitly. Assessment-key pages
have a separate 8 KiB bound and expose incomplete/refused evidence. The source
and assessment admission policies are unchanged, so existing valid admissions
do not need to be rewritten merely for these workflow helpers.

The [October 30 study](research-evidence-20261030/selection-results.md.txt)
remains frozen. New tests cover real stdio find/describe/decide, incomplete and
conflicting evidence, missing revisions, absent projects, limits and unfinished
attempts. They establish workflow behavior, not a new productivity claim.
