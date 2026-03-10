# RFC 0014: Bundle mode design

## Status
Draft

## Summary

This RFC frames bundle mode as a future transport and packaging layer for
dotrepo data beyond a single repository record.

Bundle mode should answer a narrow question:
- how can one or more dotrepo artifacts travel together as a portable unit

Bundle mode should **not** answer these different questions:
- how repositories relate to each other
- how a workspace is composed
- how authority is determined between competing records

Those remain separate concerns.

## Why

The day-one protocol centers a single canonical `.repo` file and a Git-backed
index of overlays and canonical mirrors. That is the right foundation, but it is
not the only future transport shape the ecosystem may want.

Later users may need to:
- hand an agent or tool a self-contained snapshot of dotrepo artifacts
- export a reviewed slice of the index for offline or air-gapped use
- package canonical records, overlays, evidence, and related claim artifacts for
  review or archival purposes
- move dotrepo data without requiring a full Git checkout of the source index or
  repository

Bundle mode exists to solve that transport problem without mutating the protocol
into a multi-repo relation system.

## Non-goals

This RFC does not define:
- workspace semantics
- dependency or service graph semantics
- authority or precedence changes
- automatic record merging
- a package registry or distribution service
- final archive format or compression format

Bundle mode should not become a back door for cross-repo semantics that belong
under future workspace or relations work.

## Problem statement

Bundle mode should make it possible to package dotrepo artifacts together while
preserving:
- repository identity
- trust and provenance metadata
- stable locators within the bundle
- enough context to inspect evidence, claims, and generated artifacts

Bundle mode should do that without:
- changing the meaning of the enclosed records
- silently elevating authority because records happened to arrive together
- implying relations between repositories that are merely co-packaged

## Proposed concept

A bundle is a portable container of dotrepo artifacts plus a small manifest that
describes what is inside.

The minimum conceptual pieces are:
- a bundle manifest
- one or more included artifacts
- stable internal paths or locators for those artifacts
- descriptive metadata about how the bundle was assembled

The bundle manifest should describe packaging context, not replace record-level
metadata.

## Example layout

The exact on-disk or archive format can stay open initially, but the conceptual
shape is roughly:

```text
bundle.toml
artifacts/
  repos/
    github.com/
      acme/
        widget/
          .repo
          record.toml
          evidence.md
          claims/
            2026-03-10-maintainer-claim-01/
              claim.toml
              review.md
              events/
                0001-submitted.toml
```

This example is illustrative, not final. The important point is that a bundle
preserves recognizable dotrepo artifacts rather than inventing a totally new
internal schema.

## Bundle manifest responsibilities

The bundle manifest should answer packaging questions such as:
- what kind of bundle this is
- when it was assembled
- what repository identities or claim artifacts are included
- what the bundle considers the included root paths
- what source index or repository snapshot it was assembled from, when known

It should not replace the enclosed records' own `record.status`,
`record.source`, or `[record.trust]`.

## Bundle kinds

The design pressure suggests at least three future bundle kinds:

### 1. Repository snapshot bundle

Packages the artifacts for one repository identity.

Possible contents:
- canonical `.repo`
- generated compatibility surfaces
- overlay or canonical mirror for comparison
- evidence or claim artifacts when relevant

### 2. Index slice bundle

Packages a selected subset of index artifacts for several repository identities.

Possible uses:
- offline review
- curated distribution
- air-gapped or agent-local inspection

### 3. Review bundle

Packages the artifacts needed for a specific review workflow, such as maintainer
handoff or claim inspection.

Possible contents:
- targeted overlays
- claim artifacts
- canonical mirror references
- review notes

These kinds are conceptual categories for future planning, not a frozen
enumeration.

## Trust and provenance implications

Bundle mode must preserve the project's existing trust discipline.

### Bundles do not upgrade authority

Authority still comes from the enclosed records:
- canonical records stay canonical
- overlays stay overlays
- reviewed or verified overlays stay at their own authority level

A bundle should not make an overlay more authoritative merely because it was
distributed by a trusted party.

### Bundles preserve conflicts, they do not resolve them

If a bundle contains multiple competing records for the same repository identity:
- existing precedence and conflict rules still apply
- equal-authority conflicts remain parallel claims
- missing or `unknown` fields should not be silently backfilled

Bundle assembly is not a license to flatten disagreement.

### Bundle provenance is additive, not substitutive

A later bundle manifest may carry packaging provenance such as:
- who assembled the bundle
- when it was assembled
- what source repository or index snapshot it came from

That context is useful, but it does not replace record-level provenance inside
`[record.trust]`.

## Relationship to generated surfaces

Generated surfaces may be included in bundles as artifacts, but they should not
outrank the record that generated them.

For example:
- a bundled `README.md` is still a compatibility artifact
- a bundled `CODEOWNERS` file is still not canonical authority over the record
- bundle consumers should continue to treat `.repo` or `record.toml` as the
  semantic source

## Relationship to claims

Bundle mode may eventually carry claim artifacts, but it does not change claim
workflow semantics.

That means:
- accepted claims still do not become canonical authority by themselves
- superseded overlays remain superseded even when packaged in the same bundle as
  the resulting canonical record
- claim history should remain visible through the included claim artifacts rather
  than being collapsed into a bundle-level summary alone

## Bundle mode vs workspace and relations support

Bundle mode is about **transport**.

Workspace and relations support are about **meaningful cross-repository
structure**.

The distinction should stay explicit:
- bundle mode says what artifacts travel together
- relations say how repositories or components refer to each other
- workspace support says how multiple projects compose operationally

A bundle may contain several related repositories, but that packaging choice does
not itself define a workspace or relation graph.

## Suggested guardrails

Future implementation work should keep these guardrails:
- prefer preserving existing artifact formats over inventing bundle-only record
  dialects
- do not infer authority from bundle publisher alone
- do not use bundles to smuggle in workspace semantics early
- do not make the first bundle format depend on a public registry or service
- keep bundle import or export compatible with the existing trust and query model

## Open questions

Later design or implementation work will still need to answer:
- should the first bundle be a directory, tarball, zip, or another container
- should bundle manifests carry hashes for included artifacts
- how should canonical and overlay paths be normalized inside bundles
- whether bundles should support partial extraction or streaming inspection
- whether claim or evidence artifacts need explicit bundle-level indexing

## Recommended deferrals

The first bundle work should defer:
- signatures or cryptographic attestation at bundle level
- remote distribution protocols
- automatic workspace graph generation
- bundle-aware editor or LSP authoring
- automatic bundle merging

Those are important future topics, but not necessary to define the core problem.

## Relationship to future work

This RFC frames bundle mode as a packaging concern and explicitly separates it
from workspace and relations design.

Follow-on work should refine:
- workspace and relations model design
- first bundle manifest shape
- bundle import/export ergonomics
- trust-preserving bundle validation rules
