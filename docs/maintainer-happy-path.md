# Maintainer happy path

Use a root `.repo` as the structured source for the metadata and documentation
you choose to manage. This guide follows the current source branch; installed
binaries need [release compatibility](release-compatibility.md) and the linked
stable guide. [Installation](install.md) covers pinned binaries and CI versions.

The [native example](../examples/native-minimal/) contains a canonical manifest,
generated surfaces, and [starter CI](../examples/native-minimal/.github/workflows/dotrepo-check.yml).
When developing inside dotrepo, replace `dotrepo` with `cargo run -p dotrepo-cli --`.

## 1. Bootstrap and review

Choose one starting point:

- `dotrepo --root <repo> init`: author a starter native manifest
- `dotrepo --root <repo> import`: import conventional repository material
- `dotrepo --root <repo> adopt-overlay <path-to-record.toml>`: copy an overlay's
  facts into a native draft

Review the facts, sources, commands, and trust metadata before relying on them.
`adopt-overlay` clears overlay authority fields and status; it does not claim
canonical authority. Native mode alone does not win record selection.

## 2. Inspect and choose documentation ownership

```bash
dotrepo --root <repo> validate
dotrepo --root <repo> trust
dotrepo --root <repo> adoption-status
dotrepo --root <repo> doctor --json
dotrepo --root <repo> preview --surface contributing --json
```

Native import enables full generation only when existing files match the
renderer closely enough. Rich handwritten surfaces remain skipped until
explicitly adopted. `preview` shows proposed content and whether prose would be
dropped; `doctor` reports ownership/layout states.

For supported Markdown files, use a managed region to retain surrounding prose:

```bash
# Set compat.github.contributing = "generate" in .repo first.
dotrepo --root <repo> manage contributing --adopt
dotrepo --root <repo> generate --check
```

README, SECURITY, and CONTRIBUTING support partial management. SECURITY and
CONTRIBUTING need their corresponding `compat.github.* = "generate"` setting.
CODEOWNERS and PR templates support full generation only; enable them only when
the renderer produces the whole file you want. Malformed or ambiguous layouts
require repair before generation. The exact states, JSON reports, and limits
live in [sync boundaries](sync-boundaries.md).

## 3. Keep the local and CI loop green

```bash
dotrepo --root <repo> validate
dotrepo --root <repo> query repo.build --json
dotrepo --root <repo> trust
dotrepo --root <repo> adoption-status
dotrepo --root <repo> doctor
dotrepo --root <repo> generate --check
```

`validate` checks structure; `query` and `trust` preserve selection/conflicts;
`adoption-status` checks native validation, claim identity, starter CI, and surface
readiness. `generate --check` fails on managed/generated drift while preserving
unmanaged prose. Generator-version-only banner changes are not semantic drift.

Use `query --raw` for scalar scripting only when a single matching record exists;
it refuses competing records to avoid discarding trust context. When drift is
intentional, change `.repo` and run `generate`, then inspect the resulting diff.

Create the starter GitHub Actions workflow with a published stable version:

```bash
dotrepo --root <repo> ci init --version 1.0.1
```

The native-only scaffold installs a pinned Linux release bundle on
`ubuntu-latest`. Pass `--force` to replace an existing workflow deliberately.
The default version differs by binary release; see [installation](install.md#maintainer-ci).
Configure repository required checks separately; writing a workflow does not
make it mandatory at merge time.

MCP exposes the same readiness report as `dotrepo.adoption_status`. Current LSP
adoption hints and quick fixes can add a homepage placeholder and starter CI;
they do not verify maintainer identity or accept claims.

## 4. Request public-index authority handoff

After reviewing the native manifest and setting `repo.homepage` to the repository
identity, scaffold and submit a claim:

```bash
dotrepo --root <repo> claim-from-native \
  --index-root <index> --claim-id <claim-id> \
  --claimant-name "<maintainer name>" --review-md
dotrepo --root <repo> claim-submit-native \
  --index-root <index> --claim-id <claim-id>
```

These helpers derive identity and claim paths from the native record. Submission
does not grant canonical authority; the operator must review the claim and its
evidence. Once that review permits acceptance, the reviewer can record links:

```bash
dotrepo --root <repo> claim-accept-native \
  --index-root <index> --claim-id <claim-id>
```

Acceptance records a canonical `.repo` path and matching index mirror path; it
does not fetch, create, or publish those artifacts. Accepted claims without
canonical links remain pending. Verify the actual upstream record and inspect
claim state/history using [the operator workflow](maintainer-claim-review-workflow.md).

Use `trust --json` or `query <path> --json` to inspect selection, superseded or
parallel records, provenance, and conflicts after handoff. A canonical record
wins only for the matching identity; missing fields are not silently backfilled
from an overlay.
