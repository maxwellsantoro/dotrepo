# RFC 0003: CLI and query contract

## Status
Draft

## Commands

### `dotrepo init`
Create a starter `.repo` file for an existing repository.

### `dotrepo import`
Bootstrap a draft `.repo` or overlay `record.toml` from conventional repository surfaces.

The v0.1 command should:
- read `README.md`, `CODEOWNERS`, and `SECURITY.md` when present
- default to a native draft `.repo` import
- support `--mode overlay --source <url>` to write `record.toml` plus `evidence.md`
- preserve the trust story by recording imported sources and inferred fallbacks in record metadata or evidence text

### `dotrepo validate`
Validate the record and return actionable diagnostics.

### `dotrepo validate-index`
Validate a seed/public index tree rooted at `index/`.

The v0.1 command should:
- discover `record.toml` files under `repos/<host>/<owner>/<repo>/`
- require a sibling `evidence.md`
- enforce source/path identity alignment for overlay entries
- warn when public-index records use non-reference trust vocabulary or evidence that does not explain imported, inferred, build, test, or `unknown` claims clearly

### `dotrepo query <path>`
Return a structured value for a dot path such as:
- `repo.name`
- `owners.maintainers`
- `repo.build`
- `record.trust.provenance`
- `x.example.internal_id`

The command should support:
- human-readable output by default
- `--json` for deterministic JSON output
- `--raw` for scalar values when scripts want unquoted strings

All serialized fields should be queryable by default through dot-path traversal.

Conflict-aware query responses should preserve both the preferred value and the
authority decision behind it.

For machine-readable surfaces, the query response should include:
- `path`
- the preferred `value`
- `selection`, containing:
  - the preferred record summary
  - the reason that record was selected
  - a locator for the preferred record, such as `manifestPath` or index path
- `conflicts`, containing zero or more competing claims with:
  - the competing value when the queried field differs
  - the competing record summary
  - the relationship to the preferred record (`superseded` or `parallel`)
  - the reason it did not become the preferred record

The query contract should always include `selection`. It should include `conflicts`
whenever competing records exist for the same repository identity.

`--json` should serialize the full query report object, not only the scalar value.
`--raw` remains useful for scripts, but it should refuse conflictful results rather
than silently discarding trust context. A future explicit lossy mode may relax that,
but conflict-aware query output should be safe by default.

### `dotrepo generate`
Generate synchronized repository surfaces such as README or GitHub compatibility files.

Day-one compatibility outputs may include:
- `CODEOWNERS`
- `SECURITY.md`
- `CONTRIBUTING.md`
- pull request templates

`--check` should fail if generated outputs are stale and report the full stale set in one run.

The command should resolve the manifest through the same root lookup used by validation and query commands.

### `dotrepo doctor`
Surface unmanaged files, ambiguous sync conditions, and migration hints.

At minimum, v0.1 should inspect conventional repository surfaces such as:
- `README.md`
- `CODEOWNERS`
- `SECURITY.md`
- `CONTRIBUTING.md`
- pull request templates

### `dotrepo trust`
Display the record's status, provenance, confidence, and source context in one place.

Conflict-aware trust responses should use the same `selection` and `conflicts`
structure as query responses, but without a queried field value.

For machine-readable surfaces, the trust response should include:
- the preferred record summary
- the reason it is preferred
- zero or more competing or superseded records
- enough locator information to inspect the preferred and competing records

The trust contract should not require downstream consumers to infer precedence only
from `record.status`. The response should say explicitly why one record won and which
records remain visible as lower-authority or parallel context.

## Exit codes

- `0`: success
- `1`: invalid input or runtime error
- `2`: check-mode drift or actionable mismatch detected

`validate-index` should return `0` when it only emits warnings.

## Query stability

The query contract should be stable enough for scripts, agents, and editor tooling.

`selection.reason` should use a small stable vocabulary for day-one consumers:
- `only_matching_record`
- `canonical_preferred`
- `higher_status_overlay`
- `equal_authority_conflict`

`conflicts[].relationship` should use:
- `superseded`
- `parallel`

## Output guidance

Human output should be readable. Machine output should be deterministic and schema-aware.

Worked examples for the conflict-aware response shape live in
[`docs/conflict-surfacing-examples.md`](../docs/conflict-surfacing-examples.md).
