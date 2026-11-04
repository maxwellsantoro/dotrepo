# Experimental requirement assessments

The local decision-workflow MCP service can use metadata for cheap discovery and
separately check shortlisted repositories against retained source assessments.
This experimental path adds no public protocol version and leaves the public
source-only instruction consumer unchanged.

## Two stages

Start the service with source and assessment tools explicitly enabled:

```bash
uv run --offline --no-sync python scripts/repodigest_service.py \
  --database /tmp/repodigest-qualified.sqlite \
  --allow-requirement-assessments --compiled-sources
```

The operator supplies a working database admitted through the
[source-store workflow](experimental-decision-source-cache.md); never admit new
assessments into a frozen benchmark database. If an independently prepared
metadata index is available, add `--metadata-index /path/to/discovery-index`.
The scoped source delivery includes the existing adapter, not the large
Discovery-100 databases or an automatically populated catalog. Without that
option, discovery uses the admitted source profiles.

- `dotrepo.decision.find` uses names, descriptions, topics and language metadata
  when `--metadata-index` is supplied. It returns leads and a lexical ranking,
  without a suitability score. Existing source-enriched discovery remains
  available when this option is absent.
- `dotrepo.decision.describe` returns repository evidence and assessment keys from a
  separate index of assessment-bearing components, independent of manifest
  pagination. It includes earlier assessments whose declared sources still match
  at the requested revision. Qualification reports their original assessed revision.
  Continue that index with `requirementOffset` when
  `requirementKnowledgeNextOffset` is present. Optional `revision` pins an exact
  retained revision and refuses missing evidence instead of substituting HEAD.
- `dotrepo.decision.qualify` checks 1–4 exact repository/revision/component targets
  against 1–8 boolean conditions in one request. Responses are capped at 32 KiB;
  a larger result is refused with a request to narrow the comparison.
- `source.read` provides original passages when the caller needs more context.

The [bounded selection workflow](experimental-decision-selection.md) combines
these primitives into a shortlist, explicit stopping rule and preliminary final
decision. It retains unfinished attempts separately from completed decisions.

The metadata catalog and source store can have different coverage and revisions.
A metadata lead does not establish that a current source assessment exists.
Describe returns the source revision to use for qualification; the caller must
decide whether that revision suits the actual task.

A qualification request has this form:

```json
{
  "candidates": [{
    "repository": "github.com/microsoft/markitdown",
    "revision": "7482c092d9c0074a89803c9fdb63a969e7fe17fc",
    "component": "packages/markitdown"
  }],
  "requirements": [
    {"key": "conversion.docx-to-markdown", "expected": true},
    {"key": "external.libreoffice.required", "expected": false}
  ]
}
```

Claim keys are exact experimental identifiers, not a universal vocabulary.
The caller must align a claim's meaning, component, basis and limitations with
the user's requirement. There is no free-text requirement interpretation or
lookup-time model call. Missing keys require further investigation.

## What the answers mean

| Result | Meaning |
| --- | --- |
| Supported | Current, scoped source assessments agree with the requested value. |
| Contradicted | Current, scoped source assessments explicitly establish the opposite value. |
| Unknown | Evidence is absent, stale, conflicting, invalid or unavailable. |

Each matching assessment includes its basis, reasoning, limitations, source
paths, full body hashes, line ranges and short excerpts. Excerpts are explicitly
marked when truncated; full source remains separately readable. Conflicting
assessments are retained and return unknown rather than selecting a winner.

`publisher-declaration` means the inspected documentation declares the
capability. `source-analysis` means a reviewer derived the finding from
inspected source, such as a declared interpreter range. Neither is an execution
receipt. Source silence cannot establish that a dependency is absent or a
capability unsupported. The response always grants no execution authorization.

## Admission and invalidation

The separate operator command admits a small assessment after a review:

```bash
uv run --offline --no-sync python scripts/repodigest_requirements.py \
  --database /tmp/repodigest-qualified.sqlite \
  --assessment assessment.json --review review.json
```

The [development input](research-evidence-20261030/requirements-assessment.json)
shows the three required target fields and claims with boolean value, explicit
basis, bounded reason, limitations and 1–4 source references. A review must
approve the SHA256 of the exact input bytes and identify its reviewer.

Admission mechanically verifies source hashes and line bounds against previously
admitted source, then retains the input, review and compiled record as immutable
objects. It preserves the original component/revision and binds interpretation
to the declared source hashes, source policy and assessment-reader policy.
Timestamp-only record changes do not invalidate it. At a separately admitted
new revision, the same scoped assessment can be reused only when every declared
source remains inspected, retained and byte-identical. The original
`assessedRevision` remains visible; this is not a claim that the assessment was
reviewed again. Source status is `current`, `changed` or `unknown`, independently
of the requirement outcome. Only source-current assessments contribute to
`supported` or `contradicted`; historical changed/unknown assessments remain
visible. Admission-policy changes require re-admission, and the service makes
no live network freshness check. The admitted source observation must still
satisfy the existing 30-day freshness bound.

Assessment authors must declare every source dependency their interpretation
needs. Matching those bytes does not prove the interpretation or any external
premise remains true; undeclared dependencies cannot be checked automatically.

**The trusted operator chooses the reviewer.** The JSON approval does not prove
semantic entailment, authenticate a reviewer, or establish reviewer independence.
The operator is responsible for those decisions. An automated independent review
is not the public protocol's human `reviewed` status. This path does not mint
public trust labels.

Lookup validates compact record hashes, admitted source-inventory hashes and
retained-body presence without reopening raw source bodies or replaying the
importer. Body integrity is checked when source content is read. It performs no network, model or
upstream execution. Assessment creation, review, refresh and consumer verification
still have costs and must be included in a future total-work comparison.

## Retained example and remaining evaluation

The [development packet](research-evidence-20261030/requirements-readme.md.txt)
uses the illustrative document-conversion case to check supported, contradicted
and unknown responses through actual MCP calls. It is a development example,
not an independently selected user task or a productivity study.

The [subsequent twelve-session comparison](research-evidence-20261030/selection-results.md.txt)
tested independently authored requirements with task-conditioned cohort
enrichment. It reduced source reading in two completed pairs but did not
establish token-efficiency or net economics; seven attempts were incomplete.
The new bounded workflow addresses observed friction. Future benefit claims need
fresh tasks and complete investigation, verification, usage, acquisition,
assessment and refresh accounting. Discovery-100 and F-05 retain their outcomes.
