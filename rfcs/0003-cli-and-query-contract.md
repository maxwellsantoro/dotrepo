# RFC 0003: CLI and query contract

## Status
Draft

## Commands

### `dotrepo init`
Create a starter `.repo` file for an existing repository.

### `dotrepo validate`
Validate the record and return actionable diagnostics.

### `dotrepo query <path>`
Return a structured value for a dot path such as:
- `repo.name`
- `owners.maintainers`
- `repo.build`
- `record.trust.provenance`
- `x.example.internal_id`

The command should support human-readable output and `--json`.
All serialized fields should be queryable by default through dot-path traversal.

### `dotrepo generate`
Generate synchronized repository surfaces such as README or GitHub compatibility files.

`--check` should fail if generated outputs are stale and report the full stale set in one run.

### `dotrepo doctor`
Surface unmanaged files, ambiguous sync conditions, and migration hints.

At minimum, v0.1 should inspect conventional repository surfaces such as:
- `README.md`
- `CODEOWNERS`
- `SECURITY.md`
- `CONTRIBUTING.md`

### `dotrepo trust`
Display the record's status, provenance, confidence, and source context in one place.

## Exit codes

- `0`: success
- `1`: invalid input or runtime error
- `2`: check-mode drift or actionable mismatch detected

## Query stability

The query contract should be stable enough for scripts, agents, and editor tooling.

## Output guidance

Human output should be readable. Machine output should be deterministic and schema-aware.
