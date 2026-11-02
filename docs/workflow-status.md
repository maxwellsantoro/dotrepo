# Workflow delivery and evidence

This source checkout combines public DotRepo contracts and local RepoDigest
experiments. Source edits, local tests, public deployments and package releases
are separate events. The November 2 workflow changes are prepared locally;
they are not in a published package or live service.

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

The companion PageDigest repository implements the web adapter and publisher
generator/Astro path. Its local recurring workflow reports body changes,
rereading needs and source-bound findings. DotPage is a publisher-facing role,
not a requirement for another service or a second manually maintained page list.
A common cross-domain service remains a design option, not completed infrastructure.

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
