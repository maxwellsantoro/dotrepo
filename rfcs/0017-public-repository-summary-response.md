# RFC 0017: Public repository summary response

## Status
Accepted for `v0` public contract

This RFC now describes the accepted `v0` repository-summary contract.

Compatibility rule:
- existing summary semantics are frozen within `apiVersion = "v0"`
- additive fields are allowed within `v0` only when they do not rename, remove,
  or reinterpret existing keys
- breaking field-shape changes require a new public `apiVersion`

For the exact checked-in `v0` key/link contract, see
[`docs/public-api-compatibility.md`](../docs/public-api-compatibility.md).

## Summary

This RFC defines the first concrete response shape for:

- `GET /v0/repos/{host}/{owner}/{repo}`

The day-one goal is narrow:
- answer what dotrepo knows about one repository identity
- reuse existing selection, conflict, trust, and claim-visibility semantics
- stay read-only and avoid inventing a public-only truth model

This endpoint is the public-serving wrapper over existing index semantics. It is
not a replacement for the local `trust` or `query` contracts.

## Why

RFC 0016 defines the direction for a public, identity-first, read-only serving
surface, but it stops short of naming the concrete repository-summary payload.

That payload is the first public contract that:
- public repository detail pages can render directly
- agents can inspect without cloning the index
- later trust and query endpoint wrappers can align around

If the summary shape stays vague, the public site and API will drift toward
bespoke product-language instead of staying anchored to the protocol.

## Design principles

### Reuse selection and conflict semantics directly

The repository summary should preserve:
- `selection.reason`
- `conflicts[].relationship`
- selected and competing record summaries
- claim context when it changes current visibility

The public response may wrap those structures, but it should not reinterpret
them.

### No silent backfill across competing records

The summary endpoint should never synthesize a "best of all records" profile.

If the preferred record is missing a field:
- that field stays absent in the repository summary
- conflicting records remain visible under `conflicts[]`
- clients can inspect the conflict set or use the query endpoint later

This preserves the same no-silent-merge rule as local trust and query surfaces.

### Summary-first, not full-manifest-in-disguise

The repository summary should expose a stable, high-signal subset of common
repository facts for a detail page:
- identity
- name and description
- homepage and documentation entry points
- high-signal ownership and security-contact hints
- record-selection and conflict context

It should not try to mirror every manifest field. Arbitrary or deeper field
inspection belongs to the public query wrapper.

## Recommended response shape

```json
{
  "apiVersion": "v0",
  "freshness": {
    "generatedAt": "2026-03-10T18:30:00Z",
    "snapshotDigest": "3c29d77b5b1f...",
    "staleAfter": "2026-03-11T18:30:00Z"
  },
  "identity": {
    "host": "github.com",
    "owner": "acme",
    "repo": "widget",
    "source": "https://github.com/acme/widget"
  },
  "repository": {
    "name": "Widget",
    "description": "Trust-aware widgets for build automation.",
    "homepage": "https://acme.dev/widget",
    "docsRoot": "https://acme.dev/widget/docs",
    "gettingStarted": "https://acme.dev/widget/docs/getting-started",
    "ownersTeam": "@acme/widget-team",
    "securityContact": "security@acme.dev"
  },
  "selection": {
    "reason": "canonical_preferred",
    "record": {
      "manifestPath": "/index/repos/github.com/acme/widget/record.toml",
      "record": {
        "mode": "overlay",
        "status": "canonical",
        "source": "https://github.com/acme/widget",
        "trust": {
          "confidence": "high",
          "provenance": [
            "declared"
          ],
          "notes": "Canonical mirror preferred over older overlay history."
        }
      },
      "claim": {
        "id": "github.com/acme/widget/2026-03-10-maintainer-claim-01",
        "state": "accepted",
        "handoff": "superseded",
        "claimPath": "/index/repos/github.com/acme/widget/claims/2026-03-10-maintainer-claim-01/claim.toml",
        "latestEvent": "/index/repos/github.com/acme/widget/claims/2026-03-10-maintainer-claim-01/events/0004-accepted.toml",
        "reviewPath": "/index/repos/github.com/acme/widget/claims/2026-03-10-maintainer-claim-01/review.md"
      },
      "artifacts": {
        "evidencePath": "/index/repos/github.com/acme/widget/evidence.md"
      }
    }
  },
  "conflicts": [
    {
      "relationship": "superseded",
      "reason": "canonical_preferred",
      "record": {
        "manifestPath": "/index/repos/github.com/acme/widget/overlays/reviewed.toml",
        "record": {
          "mode": "overlay",
          "status": "reviewed",
          "source": "https://github.com/acme/widget"
        },
        "artifacts": {
          "evidencePath": "/index/repos/github.com/acme/widget/overlays/reviewed-evidence.md"
        }
      }
    }
  ],
  "links": {
    "self": "/v0/repos/github.com/acme/widget",
    "trust": "/v0/repos/github.com/acme/widget/trust",
    "queryTemplate": "/v0/repos/github.com/acme/widget/query?path={dot_path}",
    "indexPath": "/index/repos/github.com/acme/widget/"
  }
}
```

## Field definitions

### `apiVersion`

Day-one public serving version. This should track the public API contract, not
the internal RFC number.

### `identity`

Required identity block for the repository being inspected.

Required fields:
- `host`
- `owner`
- `repo`

Optional field:
- `source`

`source` should be present when dotrepo can point to a stable upstream locator
for the repository identity.

### `freshness`

Shared freshness metadata for the served response.

This block should follow RFC 0018:
- `generatedAt`
- `snapshotDigest`
- `staleAfter` when the serving layer wants to communicate an advisory refresh
  boundary

### `repository`

High-signal summary fields derived from the selected record only.

Recommended day-one fields:
- `name`
- `description`
- `homepage`
- `docsRoot`
- `gettingStarted`
- `ownersTeam`
- `securityContact`

Rules:
- fields should be omitted when unavailable
- fields should not be backfilled from lower-authority conflicts
- fields should use public-friendly names, but each should map to a stable local
  dot-path

Recommended dot-path mapping:
- `name` -> `repo.name`
- `description` -> `repo.description`
- `homepage` -> `repo.homepage`
- `docsRoot` -> `docs.root`
- `gettingStarted` -> `docs.getting_started`
- `ownersTeam` -> `owners.team`
- `securityContact` -> `owners.security_contact`

Build and test commands should remain out of the day-one summary shape. Those
are better served through the later public query and trust wrappers when a
consumer intentionally asks for them.

### `selection`

The same selection model already used by local trust and query surfaces.

Required:
- `selection.reason`
- `selection.record`

Day-one vocabulary should remain:
- `only_matching_record`
- `canonical_preferred`
- `higher_status_overlay`
- `equal_authority_conflict`

### `selection.record`

The recommended public shape should reuse the existing selected-record summary
and extend it only with stable artifact locators.

Required:
- `manifestPath`
- `record`

Optional:
- `claim`
- `artifacts`

`record` should keep the existing record-summary shape:
- `mode`
- `status`
- `source`
- `trust`

The public response should not invent a second abbreviated trust vocabulary.

### `selection.record.artifacts`

Optional locator block for index artifacts relevant to the selected record.

Recommended day-one fields:
- `evidencePath`
- `canonicalMirrorPath`

Additional claim-related paths should continue to live inside the nested
`claim` block rather than being duplicated here.

### `conflicts`

Conflict summaries should remain compatible with the local conflict model.

Each conflict should preserve:
- `relationship`
- `reason`
- `record`

Day-one `relationship` vocabulary should remain:
- `superseded`
- `parallel`

The summary endpoint should not flatten `parallel` conflicts into one synthetic
winner. When equal-authority disagreement exists, one record may still be
selected by stable ordering, but the disagreement must remain visible.

### `links`

Public-serving navigation links for related read-only surfaces.

Recommended day-one fields:
- `self`
- `trust`
- `queryTemplate`
- `indexPath`

`queryTemplate` is preferred over a partially specified concrete URL because the
caller still needs to provide a dot-path.

## Compatibility with existing claim visibility rules

When claim workflow affects current visibility, the selected or competing record
summary should retain the existing nested `claim` block described in RFC 0012.

The repository summary should not become a claim-ledger endpoint. It should only
surface claim context when it explains current selection or supersede state.

## Worked examples

### No conflict, overlay only

Expected properties:
- one `selection.record`
- empty `conflicts`
- no synthetic claim or supersede state

### Canonical record superseding a reviewed overlay

Expected properties:
- `selection.reason = "canonical_preferred"`
- canonical record visible in `selection.record`
- superseded overlay visible under `conflicts[]`
- claim context attached only where it explains the handoff

### Equal-authority overlay disagreement

Expected properties:
- `selection.reason = "equal_authority_conflict"`
- one selected record chosen by stable ordering
- at least one `parallel` conflict preserved
- repository summary fields sourced only from the selected record

## Explicit deferrals

This RFC does not define:
- free-form search or browse responses
- query-path response shapes beyond the link template
- freshness and staleness metadata
- public mutation or submission APIs
- public claim-history ledger responses
- final HTML page layout

Those belong to follow-on work after the repository-summary contract is stable.

## Relationship to RFC 0016

RFC 0016 defines the overall public-serving direction.

This RFC narrows that direction into the first concrete repository-summary
payload so follow-on trust and query endpoint wrappers can build on a stable
identity-first response shape.

Freshness metadata and static-serving assumptions are defined by RFC 0018.
