# Decision after the bounded recipe trial

The engineering question is resolved for this development task: an attributed
synthesized recipe can run the complete pinned iniconfig suite in a bounded,
observed environment. The current public consumer correctly abstains because
its accepted source-extraction contract does not represent this evidence type.
The next choice changes what the product is willing to represent and test.

## Recommendation

Authorize a **separate, local experimental observed-recipe capsule contract**,
with its own evaluator and disjoint future qualification tasks. Preserve the
existing source-fact consumer unchanged. This is a design and bounded prototype
decision, not approval to publish, relax confidence gates, or launch F-05.

The smallest useful contract would make the following bindings explicit:

| Binding | Required content |
| --- | --- |
| Task | Repository, commit/root tree, purpose, scope, component, working directory. |
| Recipe | Ordered argv arrays for setup/test; environment transitions and prerequisites. |
| Origin | `synthesized`; exact source hashes and author attribution, distinct from extraction. |
| Environment | Immutable image/platform, interpreter hash/version, Git/tag context, dependency evidence. |
| Observation | Assigned runs, failures, separate amendments, exact test oracle, logs and provenance. |
| Isolation | Resource limits, pre-import/after-test network observations, timeout/teardown receipts. |
| Assessment | Separate reviewer and disposition; hashes bind assessment to the complete packet. |
| Invalidation | Any changed binding invalidates reuse until separately assessed. |

In this prototype, selection should return an evidence-bearing plan for a trusted
caller to assess. It must not convert observed execution into execution permission
or label synthesized commands as extracted. Missing environment/build context
must remain explicit. The first prototype can cite this frozen packet as a
development fixture, but cannot count it as held-out qualification.

Before expanding beyond a prototype, freeze a disjoint qualification set and
failure criteria. Include wrong revision/environment, incomplete setup, missing
parameter cases, import from an installed unrelated package, amended evidence,
and failed teardown. Actual setup/execution authority and budgets must be explicit
per task. Net consumer benefit needs a later competent baseline with publisher,
indexer, maintenance and fallback costs included; this packet does not supply it.

## Alternatives

1. **Keep Digest Exchange source-only.** Archive this recipe observation as
   evidence, retain abstention, and seek source-declared complete instructions on
   different tasks. This preserves the current product boundary but leaves useful
   synthesized execution evidence outside its accepted instruction contract.
2. **Prototype observed recipes separately — recommended.** Review and implement
   the bounded contract above locally, then decide whether independent results
   justify a public design proposal. Production contracts stay unchanged during
   the experiment.
3. **Require maintainer-declared instructions first.** A maintainer could publish
   a complete applicable recipe, allowing a future source-extraction assessment.
   That requires upstream participation; no outreach or upstream change is part
   of the current authority.

## Project readiness at this boundary

| Workstream | Current evidence | Ready for |
| --- | --- | --- |
| PageDigest P1 | Defined correctness checks pass; 3,802,164 response bytes versus 2,744,160 for HTTP freshness, 38.6% more. | Reviewing the negative savings result and a differently justified hypothesis; current 20% savings gate fails. |
| DotRepo R1 | Three development tasks yield useful partial leads, zero complete qualified instructions. | Retained source/evidence and binding work; no autonomous-use benefit claim. |
| Iniconfig source closure | All 16 tracked blobs and full tree verified; original wheel/sparse CI applicability remains partial. | Source-frontier evidence reuse at the pinned identity. |
| Iniconfig synthesized execution | Final amended protocol passes 2/2 with 54 cases each; independent review accepts the bounded tuple. | A development fixture for the separate observed-recipe contract, if selected. |
| Current public consumer | Actual Rust export/reference selection abstains on inferred recipe evidence. | Continuing its existing extracted-instruction policy. |
| F-05 / production rollout | Environment, qualification and economic evidence remain incomplete. | No launch at this checkpoint. |

The requested autonomous continuation reaches a real review decision here.
Additional repeats of the same task would not choose among these product
boundaries. Choose the contract direction before changing representation,
qualification cohorts or consumer policy.
