# RFC 0020: Multi-ecosystem build/test candidates

## Status
Implemented

## Summary

This RFC adds two optional, additive `[repo]` fields:

- `build_candidates`: an array of `{ command, ecosystem, source }` entries
- `test_candidates`: same shape, for `test`

These are populated only when no single `repo.build` or `repo.test` command
could be honestly chosen as primary because the repository has more than one
legitimate, mutually exclusive command at the same tier (typically a genuinely
polyglot repository, e.g. a Rust component and a Node.js component in the same
repo). In that case `repo.build`/`repo.test` remain `None` -- that absence is
still the honest top-level answer -- but the concrete candidate commands that
were actually found are preserved in structured form instead of being
discarded.

## Why

Investigating a batch of records that regressed during an unrelated re-crawl
(see the historical crawler fix for `SUPPLEMENTAL_ROOT_FILES` and the
downgrade-guard work) surfaced a recurring pattern: the deterministic importer
finds two or more command candidates from different ecosystem manifests (e.g.
`Cargo.toml` and `package.json` both define a `build`), correctly determines
neither should win over the other, and escalates to a model. A capable model
correctly identifies the repository as genuinely polyglot and returns a
confident "no single answer is honest" -- which is the right call. But the
existing pipeline then discarded the very candidates that made the answer
possible, leaving a human or agent consuming the record with nothing more than
an absent field.

A quick census across the checked-in index at the time found this pattern in
roughly 4% of records (23 of 613), via the "suggested conflicting build/test
commands" evidence text emitted before model escalation runs. That is common
enough to deserve a first-class, structured answer rather than being treated
as an edge case.

## Design

### Why not just pick one command anyway

Picking an arbitrary winner (e.g. "prefer Rust over Node.js") would produce a
plausible-looking but potentially wrong or incomplete answer for repositories
where a maintainer, agent, or CI system might need the *other* command. It
also cuts against the project's non-negotiable principle that generated prose
and inference must not fabricate completeness to improve coverage metrics.

### Why not a structured `repo.build`/`repo.test`

Changing `build`/`test` from a `String` to a richer structure would be a
breaking change for the overwhelming majority of records where a single
command is genuinely correct and unambiguous. Keeping them as simple optional
strings preserves that common case exactly as-is; the candidates arrays are
purely additive for the minority case where ambiguity is real.

### Field shape

```toml
[repo]
# ... build and test remain unset in the ambiguous case ...

[[repo.test_candidates]]
command = "npm test"
ecosystem = "Node.js"
source = "package.json"

[[repo.test_candidates]]
command = "python -m pytest"
ecosystem = "Python"
source = "pyproject.toml"
```

- `command`: the concrete, sanitized shell command (passes the same
  shell-safety check applied to `repo.build`/`repo.test`)
- `ecosystem`: a best-effort human-readable label inferred from `source`'s
  filename (e.g. `Cargo.toml` -> `"Rust"`, `package.json` -> `"Node.js"`).
  `None`/absent when the source file isn't a recognized manifest (e.g. an
  arbitrary CI workflow file) -- this is a display aid, not a validated
  taxonomy, and unrecognized sources are not guessed at.
- `source`: the repository-relative path the candidate was found in.

Both arrays are empty by default and omitted from serialized output when
empty (`skip_serializing_if = "Vec::is_empty"`), so every existing record and
fixture remains byte-identical until a repository actually needs this field.

### Population point

Both arrays are populated in one place: `apply_adjudication_to_import_plan`'s
`AdjudicationOutcome::Absent` branch, in `dotrepo-core`. This function is the
single choke point for every escalation outcome (deterministic tier walk,
primary/second-opinion/API model tiers, and any future tier), so this covers
every path that can produce an honest "no single answer" without needing to
duplicate the logic per tier.

Candidates are deduplicated by (sanitized) command value and filtered through
the same `sanitize_import_command` check used for `repo.build`/`repo.test`
directly, so an unsafe shell-like candidate is dropped rather than preserved.
`validate_manifest` also independently checks every stored candidate command
for shell safety, so a hand-authored native `.repo` cannot smuggle an unsafe
command into these fields either.

## Public surface

`profile.json`'s `research.execution` section gains the same two arrays
(`buildCandidates`/`testCandidates`, camelCase per the existing public
convention) with the same `{ command, ecosystem, source }` shape. This makes
the preserved candidates visible to the same consumers (CLI query, MCP tools,
public API, website) that already read `execution.build`/`execution.test`.

## Non-goals

- This does not attempt to choose a "best" candidate automatically; that
  remains a human or downstream-tool decision.
- This does not extend to other ambiguous fields (e.g. `owners.team`) in this
  pass. If the same pattern recurs elsewhere, it should get its own evaluation
  rather than a blanket "candidates array for everything" convention.
- This does not change scoring: a record with only `build_candidates`
  populated (and `build` absent) scores identically to any other honest
  absence for promotion purposes.

## Backfill

Existing records that hit this pattern before this RFC landed have `build`/
`test` unset with no candidates recorded. They will pick up populated
candidate arrays the next time they are re-crawled (routine refresh or
deliberate re-crawl); this RFC does not mandate an immediate index-wide
backfill.
