# RFC 0021: Value-bound execution context

## Status

Implemented: additive authoring, validation, query, and public export contract,
plus conservative extraction of explicitly scoped documentation blocks as
candidates. General nested-manifest context extraction remains deferred.
The October 4 Sonnet audit exercises source-inspected candidate authoring in the
index while withholding the setup-only scalar and limiting the actual command's scope.

## Contract

Scalar `repo.build` and `repo.test` retain their repository-default meaning.
Optional `repo.build_context` and `repo.test_context` describe the exact scalar
value. Each RFC 0020 command candidate may carry an optional `context` with the
same shape. Existing records serialize unchanged when context is absent.

```toml
[[repo.test_candidates]]
command = "npm test"
ecosystem = "Node.js"
source = "packages/ui/package.json"

[repo.test_candidates.context]
command = "npm test"
working_directory = "packages/ui"
scope = "component"
component = "packages/ui"
prerequisites = ["Install Node.js and run npm ci in packages/ui"]
source = "CONTRIBUTING.md"
```

| Field | Meaning and validation |
| --- | --- |
| `command` | Exact associated scalar or candidate string without surrounding whitespace; removal or any text change invalidates retained context |
| `working_directory` | Explicit normalized repository-relative directory; `.` denotes the root |
| `scope` | `repository` or `component`; scope describes coverage, independently of where the command runs |
| `component` | Required non-root repository-relative directory for component scope; omitted for repository scope |
| `prerequisites` | Explicit list of nonempty source-grounded descriptions; `[]` declares no known prerequisites, not that setup has succeeded |
| `source` | Repository-relative file declaring the context; it may differ from the candidate's command source |

All fields except `component` are required within a present context. Unknown
context keys fail parsing so a misspelled scope or directory cannot be ignored.
Path strings use `/` separators and forbid absolute paths, drive prefixes,
backslashes, traversal, empty segments, dot segments, and control characters.
Native paths additionally resolve to contained files/directories; overlay paths
refer to upstream and are never resolved against the index checkout.

Scalar context must declare repository scope and root working directory.
Component context belongs on candidates. A component command can run from the
root, for example with an explicit manifest argument; directory and scope are
separate facts. Scalar and candidate commands retain existing shell screening.
Prerequisites are descriptions, never an automatic setup script.

## Evidence and consumer use

Context is a factual assertion whose source must support the complete tuple.
Structural validation does not prove that assertion, calibrate confidence, check
the installed environment, execute commands, or grant execution permission.
Consumers must check evidence and age, satisfy prerequisites, and explicitly
select the scope their task needs. Existing field assessments for a command
string do not independently verify newly supplied context.

Absent context leaves directory, scope, and prerequisites unassessed. Legacy
records receive no invented root directory or empty prerequisite list. The
importer continues to withhold nested, incomplete, and prerequisite-dependent
commands as scalar defaults and does not populate context by guessing.
Changing directory, component, prerequisites, or source requires inspecting the
new assertion even when the command text is unchanged. This contract does not
change promotion scoring or freshness timestamps.

### Supported documentation extraction

Automatic extraction supports one literal shell fence under `Repository build`,
`Repository tests`, `Component build: <path>`, or `Component tests: <path>`.
The heading declares scope independently of directory. Its first line must be
`cd .` for repository scope or `cd <path>` matching the component heading.
The last line is an unchanged recognized build/test entrypoint. Supported setup
lines between them become prerequisite descriptions. An empty prerequisite list
requires the explicit source statement `Prerequisites: none.`; omission cannot
establish it.

Unsupported prose, other setup sections, multiple fences, unresolved parameters,
directory disagreement, and unsafe or missing directories cause abstention.
Context extraction preserves candidates only, including repository-scoped ones;
it does not promote a scalar or mint a verification assessment. An imported
candidate still needs separately inspected, value-bound evidence before the
contextual consumer can accept it. Ordinary nested documentation and manifests
remain unassessed when they do not establish the complete tuple.

## Public compatibility

Profile `execution` optionally adds `buildContext` and `testContext`. Candidate
entries optionally add `context`. Public contexts use `workingDirectory` and
retain `command`, `scope`, `component`, `prerequisites`, and `source`. Local
queries expose manifest snake_case paths. Static query-input snapshots retain
the manifest shape; public profiles retain the camelCase shape.

These additions preserve the manifest schema and public API version. Existing
names, scalar semantics, absence, selection, and authority stay stable. Rust
`Repo` and `BuildTestCandidate` struct literals require the new optional fields
on the current development line; stable release binaries are unaffected.

The execution-context fixture and integration tests pin parsing, exact binding,
scope/path validation, native containment, absent-context compatibility, local
query, and public profile/export behavior. The public compatibility fixture
records the optional profile keys and context shape.
