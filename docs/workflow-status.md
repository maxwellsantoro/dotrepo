# Workflow delivery and evidence

This source checkout combines public DotRepo contracts and experimental RepoDigest
workflows. Source edits, local tests, public deployments and package releases
are separate events. The November 2 experimental workflows are available from
this source checkout; they are not in a released package or hosted API.
[PR208](https://github.com/maxwellsantoro/dotrepo/pull/208) records their
implementation and validation history.

| Job | Available surface | What it establishes |
| --- | --- | --- |
| Orient or discover | Existing public profiles/search and stable tools | Reported facts, source context and age; no suitability or execution guarantee |
| Shortlist | Local experimental `repodigest.shortlist` | Up to four leads from three search queries, with visible gaps |
| Qualify requirements | Local `describe`, `qualify`, `decide` | Supported, contradicted or unknown source assessments at exact revision/component scope |
| Inspect original evidence | Local retained `source.list`/`source.read`, optional separately configured HTTP fallback | Bound source bytes and passages; text remains untrusted data |
| Execute | Separate authorized task environment | A particular run in a particular environment; no lookup tool grants authority |
| Maintain publisher context | Existing native import/preview/doctor/drift, plus local publisher helper | Source-derived proposals and explicit ambiguity without overwriting adopted records |

The experimental service stays in Python/SQLite and uses the existing Rust
importer. No new `.repo` schema or public MCP version is introduced. Admission,
content hashes and exact revisions bind evidence; they do not authenticate an
independent reviewer's identity or prove semantic correctness. Record age and
export age remain distinct. Requirement checks do not query current HEAD.

## Shared direction

**Publish what you know. Reuse what still holds. Investigate what changed.**

Publishers and consumers meet in the middle: derive declarations from existing
sources, preserve the evidence behind useful work, and repeat only the work
required by changes, uncertainty and the task's assurance needs. Participation
must help both sides; moving effort onto maintainers is not a net saving.

- **DotRepo** is the existing repository protocol, toolchain and public lookup
  index. Native declarations and observed overlays retain different authority.
- **RepoDigest** is the experimental discovery, assessment and reuse workflow
  in this repository. Preliminary suitability is distinct from a successful run.
- **PageDigest** is the existing website manifest protocol and publisher/consumer
  toolchain. Its [experimental recurring workflow](https://github.com/maxwellsantoro/pagedigest/pull/2)
  retains source-bound findings and reports what needs rereading.
- **DotPage** names that project's publisher role in existing site builds. It is
  not a separately shipped product or another page catalog to maintain.

**Lazy Collective** is the chosen umbrella and local coordination project,
not a released common service or runtime. The
[PageDigest ecosystem guide](https://github.com/maxwellsantoro/pagedigest/blob/main/docs/ecosystem.md)
owns its website-specific integration and evidence.

Assurance follows the task: metadata can establish a lead; explicit requirements
need scoped source evidence; execution needs its own environment, checks and
authorization. Provenance and authenticity do not prove correctness or freshness.
Unchanged source bytes can preserve a finding's declared dependencies without
proving its interpretation or external premises. Compare completed results at
matched quality and freshness, counting publisher, indexer and consumer work,
fallback and unfinished attempts. General net savings remain unestablished.

## Latest evidence

The linked text files are verbatim compact result documents with
[original paths, commit identities and hashes](research-evidence-20261030/README.md).
Full raw studies remain on the preserved local experimental branch; they are
not included in this scoped product change or claimed to be a reproduction bundle.

- [Selection consumers](research-evidence-20261030/selection-results.md.txt):
  five accepted answers across twelve attempts; seven incomplete. Treatment
  reduced source reading in the two completed pairs but increased total native
  tokens. Whole-study usage and cost remain unknown.
- [Discovery-100 correction](research-evidence-20261030/discovery100-correction.md.txt):
  identical supported recall, 86% more response tokens for source enrichment.
- [Source-cache comparison](research-evidence-20261030/source-cache-readme.md.txt):
  cached source is useful; added facts did not reduce uncached input against the
  same cache. Acquisition and maintenance costs prevent a net savings claim.
- [Coding pilot](research-evidence-20261030/coding-pilot-results.md.txt):
  neither final patch passed the complete repository test command.
- The sibling PageDigest P1 at commit `b0da351` transferred 38.6% more response
  bytes than HTTP freshness caching at the same bounded freshness target. Its
  local report is `docs/benchmarks/digest-exchange-p1-20261029/README.md` in that checkout.

The November 2 tests are correctness/workflow controls. They are not replacement
consumer experiments, independent adoption, dollar-cost measurements or a new
positive economic result. Historical benchmark files remain unchanged.

Start with [bounded selection](experimental-repodigest-selection.md),
[requirement semantics](experimental-repodigest-requirements.md), and
[publisher setup/update](maintainer-happy-path.md). The [roadmap](../ROADMAP.md)
owns next outcome gates; [release compatibility](release-compatibility.md) owns
published versions.
