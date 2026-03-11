# RFC 0019: Public trust and query wrappers

## Status
Draft

## Summary

This RFC defines the first public wrapper shapes for:

- `GET /v0/repos/{host}/{owner}/{repo}/trust`
- `GET /v0/repos/{host}/{owner}/{repo}/query?path=...`

These wrappers are intentionally thin:
- they reuse existing local `trust` and `query` semantics
- they add only public-serving metadata such as identity, links, and freshness
- they preserve claim-aware visibility where it materially explains selection

## Why

RFC 0016 already names trust and query as day-one public surfaces. What it does
not yet define is the concrete wrapper shape for those responses.

If public trust and query responses stay underspecified, the public site and API
will drift into softer product-language that no longer matches the CLI, MCP, or
core library.

## Public trust wrapper

### Endpoint

`GET /v0/repos/{host}/{owner}/{repo}/trust`

### Recommended response shape

```json
{
  "apiVersion": "v0",
  "freshness": {
    "generatedAt": "2026-03-10T18:30:00Z",
    "snapshotDigest": "3c29d77b5b1f..."
  },
  "identity": {
    "host": "github.com",
    "owner": "acme",
    "repo": "widget",
    "source": "https://github.com/acme/widget"
  },
  "selection": {
    "reason": "canonical_preferred",
    "record": {
      "manifestPath": "repos/github.com/acme/widget/record.toml",
      "record": {
        "mode": "overlay",
        "status": "canonical",
        "source": "https://github.com/acme/widget",
        "trust": {
          "confidence": "high",
          "provenance": ["declared"]
        }
      },
      "claim": {
        "id": "github.com/acme/widget/2026-03-10-maintainer-claim-01",
        "state": "accepted",
        "handoff": "superseded",
        "claimPath": "repos/github.com/acme/widget/claims/2026-03-10-maintainer-claim-01/claim.toml"
      }
    }
  },
  "conflicts": [
    {
      "relationship": "superseded",
      "reason": "canonical_preferred",
      "record": {
        "manifestPath": "repos/github.com/acme/widget/overlays/reviewed.toml",
        "record": {
          "mode": "overlay",
          "status": "reviewed",
          "source": "https://github.com/acme/widget"
        }
      }
    }
  ],
  "links": {
    "self": "/v0/repos/github.com/acme/widget/trust",
    "repository": "/v0/repos/github.com/acme/widget",
    "queryTemplate": "/v0/repos/github.com/acme/widget/query?path={dot_path}"
  }
}
```

### Required compatibility rules

The public trust wrapper should:
- preserve `selection.reason`
- preserve `conflicts[].relationship`
- preserve full record trust metadata
- preserve nested claim context when it materially explains current visibility

The public wrapper should not:
- invent a second trust vocabulary
- suppress competing records for cosmetic reasons
- flatten superseded or parallel overlays away

## Public query wrapper

### Endpoint

`GET /v0/repos/{host}/{owner}/{repo}/query?path=...`

### Recommended response shape

```json
{
  "apiVersion": "v0",
  "freshness": {
    "generatedAt": "2026-03-10T18:30:00Z",
    "snapshotDigest": "3c29d77b5b1f..."
  },
  "identity": {
    "host": "github.com",
    "owner": "acme",
    "repo": "widget",
    "source": "https://github.com/acme/widget"
  },
  "path": "repo.description",
  "value": "Trust-aware widgets for build automation.",
  "selection": {
    "reason": "canonical_preferred",
    "record": {
      "manifestPath": "repos/github.com/acme/widget/record.toml",
      "record": {
        "mode": "overlay",
        "status": "canonical",
        "source": "https://github.com/acme/widget"
      }
    }
  },
  "conflicts": [],
  "links": {
    "self": "/v0/repos/github.com/acme/widget/query?path=repo.description",
    "repository": "/v0/repos/github.com/acme/widget",
    "trust": "/v0/repos/github.com/acme/widget/trust"
  }
}
```

### Required compatibility rules

The public query wrapper should:
- preserve the existing dot-path query model
- preserve the same `selection` / `conflicts` reasoning
- preserve competing values when they exist
- stay compatible with the local no-silent-merge rule

The public wrapper should not:
- reinterpret missing fields as empty strings
- invent a separate public path vocabulary
- flatten equal-authority conflicts into one synthetic answer

## Public query failures

Invalid query paths should fail explicitly in a public-facing machine-readable
shape such as:

```json
{
  "apiVersion": "v0",
  "freshness": {
    "generatedAt": "2026-03-10T18:30:00Z",
    "snapshotDigest": "3c29d77b5b1f..."
  },
  "identity": {
    "host": "github.com",
    "owner": "acme",
    "repo": "widget"
  },
  "path": "repo.missing_field",
  "error": {
    "code": "query_path_not_found",
    "message": "query path not found: repo.missing_field"
  }
}
```

Recommended day-one error codes:
- `query_path_not_found`
- `repository_not_found`
- `invalid_repository_identity`

The public error wrapper should stay terse and machine-readable. It should not
hide the underlying error reason behind site-only wording.

## Claim-aware visibility in ordinary public responses

Ordinary repository, trust, and query responses should only include claim
context when it materially explains current selection or visibility.

That means:
- accepted `pending_canonical`, `superseded`, `parallel`, and `disputed`
  outcomes may appear as nested claim context on selected or competing records
- rejected and withdrawn claim history should not be repeated on every ordinary
  repository response when they do not affect current visibility
- corrected outcomes should expose the current effective state, not the entire
  claim ledger

Dedicated claim-history inspection belongs to later claim-centric public
surfaces.

## Relationship to RFC 0012

This RFC does not redefine claim visibility. It applies RFC 0012 to public
wrappers.

The nested public record summaries should preserve:
- the existing `claim` block shape when present
- superseded overlays under `conflicts[]`
- parallel overlays under `conflicts[]`

## Explicit deferrals

This RFC does not define:
- search endpoints
- aggregate browse endpoints
- public claim-ledger endpoints
- mutation or submission routes
- final HTML site rendering

## Relationship to other RFCs

- RFC 0016 defines the public-serving direction.
- RFC 0017 defines the repository summary wrapper.
- RFC 0018 defines static-first serving and shared freshness metadata.
