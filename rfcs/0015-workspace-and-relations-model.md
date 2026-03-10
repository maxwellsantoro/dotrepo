# RFC 0015: Workspace and relations model

## Status
Draft

## Summary

This RFC defines the intended direction for future workspace and relations
support in dotrepo.

The core proposal is:
- keep the single-repository record as the semantic center
- treat relations as explicit, directed assertions between repository identities
- model workspace membership as the first high-value relation family
- keep bundle mode separate as a transport concern rather than a relation system

This RFC is directional. It does not commit the project to a finished multi-repo
implementation.

## Why

The current protocol is intentionally centered on one repository at a time. That
is the right v0.1 shape, but later growth needs a disciplined answer to the
obvious question: how should dotrepo represent repositories that belong to a
larger multi-repo structure?

Without that answer, future work would risk:
- turning `[relations]` into an unstructured dumping ground
- overloading bundle mode with semantic meaning it should not carry
- creating relation data that has no trust or provenance story
- undermining the single-repository clarity that currently makes dotrepo useful

## Non-goals

This RFC does not define:
- a complete graph model for all repository ecosystems
- package-manager dependency import
- automatic relation discovery
- public graph visualization
- bundle semantics
- claim or supersede semantics

## Design principles

### Single-repository records stay primary

Every repository should remain understandable in isolation.

Relations are an optional extension for additional context. They should not
become required to make one record intelligible.

### Relations are assertions, not ambient facts

A relation is a claim that one repository has a meaningful connection to another
repository identity.

That means relation data needs:
- a relation kind
- a target identity
- provenance or trust context
- optional explanatory notes

### Direction matters

Relations should be modeled as directed assertions from the current repository to
a target repository identity.

That keeps the model simple:
- this repository claims it is part of a workspace
- this repository claims another repository is its workspace root
- this repository claims a generated or source relationship to another repo

Reciprocal edges may exist later, but they should not be assumed automatically.

### Bundle mode stays separate

Bundle mode answers what artifacts travel together.

Relations answer what repositories mean to each other.

The two may interact later, but bundle inclusion must not imply a relation, and
a relation must not require co-packaging.

## The first relation family worth modeling

The first relation family worth modeling is workspace membership.

This is the most defensible early scope because it is:
- stable enough for maintainers to assert deliberately
- useful to users and agents trying to orient themselves
- less volatile than trying to encode full dependency graphs
- compatible with the current repository-identity and trust model

### Workspace-root relation

A repository may assert that it is the coordinating root of a broader workspace
or project family.

### Workspace-member relation

A repository may assert that it belongs to a workspace rooted elsewhere.

These two assertions are related, but they should remain explicit rather than
being silently inferred from one another.

## Deferred relation families

The following categories are plausible later, but should remain deferred until
the project has real ecosystem feedback:
- generated-from or source-of relationships
- spec-to-implementation relationships
- runtime or build dependency relationships
- fork lineage or succession relationships
- loose “related project” labels

These are potentially valuable, but they are also easier to get wrong, easier to
overfit, and more likely to drag the schema toward a kitchen sink.

## Proposed relation model direction

The reserved `[relations]` namespace should eventually carry a list of explicit
relation assertions.

An illustrative direction is:

```toml
[[relations.links]]
kind = "workspace_member"
target = "github.com/acme/platform"
notes = "Primary workspace root for the Acme platform repos."

[relations.links.trust]
confidence = "high"
provenance = ["declared"]
```

Or, from the root side:

```toml
[[relations.links]]
kind = "workspace_root"
target = "github.com/acme/widget"
notes = "One of the repositories coordinated by the platform workspace."

[relations.links.trust]
confidence = "medium"
provenance = ["declared"]
```

These examples are illustrative. The important design choice is that relation
assertions are:
- explicit
- directed
- identity-scoped
- trust-bearing

## Trust and provenance across relations

Relation data should not piggyback silently on record-level trust.

A repository record may be canonical while one of its relation assertions is only
imported or inferred. That distinction should stay visible.

The model direction should therefore allow relation assertions to carry their own
trust context, including:
- confidence
- provenance
- notes

That keeps relation claims compatible with the rest of the trust model instead of
turning them into unqualified graph edges.

## Validation direction

The first validation layer for relations should stay narrow.

It should check:
- the relation kind is recognized
- the target identity is structurally valid
- trust metadata is present when the relation model requires it

It should not initially require:
- reciprocal edges
- full graph completeness
- remote existence checks for the target repository
- graph-level semantic proofs

That keeps relations compatible with the current single-record validation style.

## Workspace semantics direction

The first workspace semantics should stay descriptive, not operational.

In other words:
- a workspace relation explains that repositories belong together
- it does not define how to build, version, or release them as one unit
- it does not require dotrepo to become a package manager or orchestration layer

That boundary matters because operational multi-repo workflow is much easier to
over-promise than descriptive membership.

## Relations vs claims and authority

Relations should not modify authority rules by themselves.

For example:
- a workspace root relation does not make one repo canonical for another repo's
  metadata
- a relation does not supersede overlays
- a relation does not authorize field inheritance between repositories

Authority and claim semantics remain separate.

## Relations vs bundle mode

The intended separation from [`RFC 0014`](./0014-bundle-mode-design.md) is:
- bundle mode packages artifacts together
- relations describe semantic connections between repository identities

Examples:
- two unrelated repositories may appear in the same bundle for review and still
  have no relation
- two repositories may have a workspace relation and still be distributed
  separately

## Open questions

Later work still needs ecosystem feedback on:
- whether target identity should stay a compact string or expand to a structured
  object
- whether workspace relations need a stable workspace identifier beyond a root
  repository identity
- whether root-side and member-side assertions should validate against each other
- whether relation-specific notes are enough, or whether richer relation metadata
  will be needed

## Recommended deferrals

The first relations implementation should defer:
- dependency graph ingestion
- graph visualization
- automatic relation discovery
- bundle-derived relation inference
- relation-aware editor or site UX beyond simple inspection

## Relationship to future work

This RFC defines the intended direction for the reserved `[relations]`
namespace.

Follow-on work should refine:
- the concrete schema shape for relation assertions
- how workspace relations appear in query and trust surfaces
- whether additional relation kinds are justified by real usage
