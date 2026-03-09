# RFC 0006: MCP server contract

## Status
Draft

## Summary

dotrepo should expose a thin MCP server that wraps the same trust-aware core used by the CLI.

The server's job is not to invent new semantics. It should make the existing protocol and toolchain legible to agents by exposing validation, query, trust, generate-check, and import-preview operations as structured tools.

The first reference implementation is a stdio server in `crates/dotrepo-mcp`.

## Principles

- Prefer the existing core contract over MCP-specific behavior.
- Keep read operations separate from write operations.
- Preserve record-level trust metadata alongside queried values.
- Keep import flows explicit about what was imported and what was inferred.

## Proposed tool surface

### `dotrepo.validate`

Inputs:
- `root`

Returns:
- whether the manifest is valid
- a `diagnostics` list with severity, source, message, and manifest-path context

### `dotrepo.query`

Inputs:
- `root`
- `path`

Returns:
- `path`
- the queried `value`
- `selection`, containing:
  - the preferred record summary
  - a locator for the preferred record, such as `manifestPath` or index path
  - the reason that record was selected
- `conflicts`, containing zero or more competing claims with:
  - the competing `value` when it differs for the queried field
  - the competing record summary
  - the relationship to the preferred record (`superseded` or `parallel`)
  - the reason that competing record was not preferred

The server should not return a bare value without trust context. dotrepo's query contract is useful precisely because a consumer can see whether a value came from a draft, imported overlay, inferred record, verified record, or canonical record.

### `dotrepo.trust`

Inputs:
- `root`

Returns:
- `selection`, containing:
  - the preferred record summary
  - a locator for the preferred record, such as `manifestPath` or index path
  - the reason that record was selected
- `conflicts`, containing zero or more competing or superseded records with:
  - the competing record summary
  - the relationship to the preferred record (`superseded` or `parallel`)
  - the reason that competing record was not preferred

The trust tool should mirror the same conflict-aware selection model as query. It is
the inspection surface that explains why a canonical record won, why a reviewed
overlay beat an imported overlay, or why equal-authority overlays remain unresolved.

### `dotrepo.generate_check`

Inputs:
- `root`

Returns:
- the managed outputs dotrepo expects
- the stale subset, if any

This should mirror `dotrepo generate --check` rather than writing files.

### `dotrepo.import_preview`

Inputs:
- `root`
- `mode` (`native` or `overlay`)
- `source` for overlay mode

Returns:
- the preview manifest
- `manifest_path`
- `evidence_path` when present
- preview `evidence` text for overlay imports
- `imported_sources`
- `inferred_fields`

This should wrap the same thin import pipeline as `dotrepo import`, using `README.md`, `CODEOWNERS`, and `SECURITY.md` when available.

### `dotrepo.import_write`

Inputs:
- same as `dotrepo.import_preview`
- `force`

Returns:
- the paths written
- the resulting record status and trust summary

This write tool is optional for the first server iteration. A preview-only import tool is enough to support review and agent planning while keeping mutation explicit.

## Response shape guidance

The server should return plain structured objects. It should not require consumers to parse CLI text.

The recommended shared model is:

- `selection.reason`:
  - `only_matching_record`
  - `canonical_preferred`
  - `higher_status_overlay`
  - `equal_authority_conflict`
- `conflicts[].relationship`:
  - `superseded`
  - `parallel`

Example query response with no conflict:

```json
{
  "root": "/repo",
  "manifestPath": "/repo/.repo",
  "path": "repo.build",
  "value": "cargo test",
  "selection": {
    "reason": "only_matching_record",
    "record": {
      "manifestPath": "/repo/.repo",
      "record": {
        "mode": "overlay",
        "status": "imported",
        "source": "https://github.com/BurntSushi/ripgrep",
        "trust": {
          "confidence": "medium",
          "provenance": ["imported", "inferred"],
          "notes": "Imported from public repository materials; build and test commands are inferred from the Cargo project layout; not maintainer-verified."
        }
      }
    }
  },
  "conflicts": []
}
```

Example query response when a canonical record beats an overlay:

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

Example trust response when equal-authority overlays conflict:

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

Worked examples for these shapes live in
[`docs/conflict-surfacing-examples.md`](../docs/conflict-surfacing-examples.md).

## Relationship to the CLI

The CLI remains a human-facing reference toolchain.

The MCP server should call the same `dotrepo-core` functions used by the CLI so the trust model, import heuristics, query semantics, and validation diagnostics stay aligned across both surfaces.
