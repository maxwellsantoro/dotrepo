# Conflict surfacing examples

These examples are non-normative. They illustrate the query and trust response
contract described in [`RFC 0003`](../rfcs/0003-cli-and-query-contract.md) and
[`RFC 0006`](../rfcs/0006-mcp-server-contract.md).

## Shared model

Machine-readable query and trust responses should use the same conflict-aware shape:

- `selection`
  - `reason`
  - `record`
- `conflicts`
  - `relationship`
  - `reason`
  - `record`
  - `value` for query conflicts when the field differs

`selection.reason` uses a stable day-one vocabulary:
- `only_matching_record`
- `canonical_preferred`
- `higher_status_overlay`
- `equal_authority_conflict`

`conflicts[].relationship` uses:
- `superseded`
- `parallel`

For human-facing inspection, `dotrepo trust` is the primary CLI entry point.
It should explain the selected record, why it won, and which competing records
remain visible.

## CLI inspection example

```text
$ dotrepo --root /repo trust
selected: .repo (Native, Canonical)
selection reason: canonical record preferred over lower-authority competing records
source: none
confidence: high
provenance: declared
notes: Maintainer-authored root record.
conflicts:
- repos/github.com/acme/widget/record.toml (Overlay, Reviewed)
  relationship: superseded
  reason: canonical record preferred over lower-authority competing records
  source: https://github.com/acme/widget
  confidence: medium
  provenance: imported, verified
  notes: Reviewed overlay retained for audit history.
```

## 1. Query with no competing records

```json
{
  "root": "/repo",
  "manifestPath": "/repo/.repo",
  "path": "repo.name",
  "value": "widget",
  "selection": {
    "reason": "only_matching_record",
    "record": {
      "manifestPath": "/repo/.repo",
      "record": {
        "mode": "native",
        "status": "canonical",
        "trust": {
          "confidence": "high",
          "provenance": ["declared"]
        }
      }
    }
  },
  "conflicts": []
}
```

## 2. Query when a canonical record beats an overlay

```json
{
  "path": "repo.build",
  "value": "cargo build --workspace",
  "selection": {
    "reason": "canonical_preferred",
    "record": {
      "manifestPath": "/repo/.repo",
      "record": {
        "mode": "native",
        "status": "canonical",
        "trust": {
          "confidence": "high",
          "provenance": ["declared"]
        }
      }
    }
  },
  "conflicts": [
    {
      "relationship": "superseded",
      "reason": "canonical_preferred",
      "value": "cargo test",
      "record": {
        "manifestPath": "/index/repos/github.com/acme/widget/record.toml",
        "record": {
          "mode": "overlay",
          "status": "reviewed",
          "source": "https://github.com/acme/widget",
          "trust": {
            "confidence": "medium",
            "provenance": ["imported", "verified"]
          }
        }
      }
    }
  ]
}
```

## 3. Trust inspection when overlays disagree

```json
{
  "selection": {
    "reason": "equal_authority_conflict",
    "record": {
      "manifestPath": "/index/repos/github.com/acme/widget-a/record.toml",
      "record": {
        "mode": "overlay",
        "status": "reviewed",
        "source": "https://github.com/acme/widget"
      }
    }
  },
  "conflicts": [
    {
      "relationship": "parallel",
      "reason": "equal_authority_conflict",
      "record": {
        "manifestPath": "/index/repos/github.com/acme/widget-b/record.toml",
        "record": {
          "mode": "overlay",
          "status": "reviewed",
          "source": "https://github.com/acme/widget"
        }
      }
    }
  ]
}
```

## Raw-output guardrail

`--raw` is still useful when a script wants a single scalar value. It should only be
allowed when `selection.reason = "only_matching_record"`. If competing records exist,
raw output should refuse the query rather than silently discarding trust context.
