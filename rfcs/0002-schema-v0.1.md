# RFC 0002: Schema v0.1

## Status
Draft

## Summary

The v0.1 schema focuses on essential repository metadata that passes a three-way test:
- maintainers can reasonably provide it
- tools and agents can consume it directly
- users benefit from it being standardized

## Canonical file

The canonical in-repo record is a single root `.repo` TOML file.

## Schema string contract

Schema strings use the format `dotrepo/v<major>.<minor>`.

The v0.1 reference tool accepts `dotrepo/v0.1` exactly. Future tooling should treat the major version as the compatibility boundary and document any minor-version read compatibility explicitly rather than assuming it.

## Required top-level sections

- `schema`
- `[record]`
- `[repo]`

## Optional top-level sections

- `[owners]`
- `[docs]`
- `[readme]`
- `[compat.github]`
- `[relations]`
- `[x]` for extensions

## Core fields

### `[record]`
- `mode`: `native` or `overlay`
- `status`: `draft`, `imported`, `inferred`, `reviewed`, `verified`, or `canonical`
- `source`: optional source locator for overlays
- `generated_at`: optional timestamp
- `[record.trust]`: trust metadata attached to the record itself

### `[repo]`
- `name`
- `description`
- `homepage`
- `license`
- `status`
- `visibility`
- `languages`
- `build`
- `test`
- `topics`

`build` and `test` are shell command strings intended to be run from the repository root.

### `[owners]`
- `maintainers`
- `team`
- `security_contact`

### `[docs]`
- `root`
- `getting_started`
- `architecture`
- `api`

### `[readme]`
- `title`
- `tagline`
- `sections`
- `custom_sections`

`[readme.custom_sections.<name>]` may provide either:
- `content`: inline section content
- `path`: a relative path to a section fragment file

### `[compat.github]`
Values should be string enums rather than booleans.

Examples:
- `codeowners = "generate"`
- `security = "generate"`
- `contributing = "skip"`

Future values may include `merge` or `template:<name>`.

### `[record.trust]`
- `confidence`
- `provenance`
- `notes`

For v0.1, `confidence` remains an open string field. The reference vocabulary is `low`, `medium`, and `high`, but tools should preserve unknown values even if they do not interpret them specially.

`provenance` is also open-ended in v0.1. The reference vocabulary is `declared`, `imported`, `inferred`, and `verified`; consumers may reason about those values but should preserve unknown entries.

### `[relations]`
Reserved namespace for future cross-repo and workspace semantics.

### `[x]`
Reserved extension namespace preserved by tooling but not validated as part of the core schema.

## Validation rules

Validation must be mode-aware.

- **native** records validate local file paths strictly where applicable
- **native** records validate `docs.*` paths and `readme.custom_sections.*.path` fragments when present
- **overlay** records validate schema, `record.source`, and `record.trust.provenance` but should not require the target repo filesystem to be present
