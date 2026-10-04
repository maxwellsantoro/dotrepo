# Public release checklist

The canonical review command builds, validates, packages, and smoke-tests a
public export and install artifacts:

```bash
uv run python scripts/check_release_gate.py --output-root release-gate
```

`--skip-release-bundle --skip-vsix` selects the lightweight public-only path;
`--skip-vsix` omits extension packaging only. Record omissions in validation
results. Generated `public/`, `release-gate/`, and `dist/` trees are gitignored.
See [export operations](public-export-workflow.md) for individual commands and
[Cloudflare setup](cloudflare-deploy.md) for publication and archive restoration.
Fixed historical timestamps are for deterministic review, not a fresh deploy.

## Coordinator handoff

Collect each lane's changed paths, immutable source revision, contract changes,
and narrow-check results. Run the complete gate on the combined revision once;
repeat affected checks after integration changes. Assign one release owner for
tagging, registry publication, and hosted deployment. Artifact preparation can
run alongside consumer work, but installed-version claims require actual
publication and consumer proof requires independent outcomes.

## Source and release identity

- Validate index structure and claim history; preserve evidence and explicit
  uncertainty when sources no longer justify a value.
- Check release-version and root toolchain parity. A tag, every package, and
  every release asset must identify the same version.
- Validate the stable release/backport against its immutable tag and dependency
  graph. The 1.0.2 candidate is merged into `codex/stable-1.0`, not published;
  use [release compatibility](release-compatibility.md) for its scope. Preserve
  branch-only labels and published 1.0.1 install defaults until artifacts ship.
- After publishing a stable tag, advance workspace and standalone alias to the
  next appropriate prerelease; do not reuse the published version for new source.
- Advance `DEFAULT_CI_RELEASE_VERSION` in `adoption.rs` and regenerate the native
  CI example only after the replacement release artifact exists. Update pinned
  installs, registry metadata, and [release compatibility](release-compatibility.md).

## Public artifact checks

- Metadata, inventory, file manifest, compact search data, and representative
  summary/profile/trust/relations responses come from one snapshot.
- Pointer paths, content-addressed snapshot ID, source digest, validators,
  file hashes/sizes, log, and stats are coherent. Existing history is preserved.
- Required keys/links/errors match [wire compatibility](public-api-compatibility.md)
  and the public fixture packs.
- Homepage/catalog/docs/writing/measurement pages use the export's contracts;
  generated links honor the configured base path.
- `public-profile-coverage.*` passes the versioned valid-profile, conflict,
  malformed-profile, and completeness-signal floors. Authority/high-signal counts
  are reported; the current baseline imposes no minimum verified/high-signal floor.
- Record freshness, content-quality dashboard, both cited factual-accuracy suites,
  and lookup volume/presence metrics pass their independent gates.
- Consumer-policy coverage reports accepted values and fallback reasons separately
  from presence. Acceptance is not correctness or completed-task evidence.
- Growth artifacts exclude indexed identities. An exhausted catalog can produce
  zero targets; planned capacity is not completed coverage or permission to grow.
- The public bundle extracts to a self-describing root, and private `query-input/`
  runtime inputs cover the same snapshot without public exposure.

Threshold owners are the versioned fixtures used by
[`check_release_gate.py`](../scripts/check_release_gate.py). Update a floor only
with a reviewed evidence-backed reason; do not inflate labels to retain a badge.
A fresh export cannot reset factual record age.

## Install, hosting, and publication checks

- Extracted binary smoke tests pass for `dotrepo`, `dotrepo-public-query`,
  `dotrepo-lsp`, and `dotrepo-mcp`.
- Current release packaging covers six published workspace crates plus the
  standalone CLI alias; crawler remains internal. Alias version/dependency and
  locked checks match the tag. Earlier tags may predate the alias package.
- VSIX packages successfully and matches the intended CLI/LSP release.
- Local same-origin runtime and Worker tests/smoke pass for query, batch,
  search, comparison, and relation routes.
- Before publication, restore deployed/archived history, validate the prior
  PageDigest baseline, and enforce exact-source eligibility/concurrency.
- After publication, deployed metadata, log/stats, homepage state, deterministic
  file hashes, and route smoke match the reviewed export.
- Verify scheduled refresh/canary outcomes and required-check settings rather
  than inferring them from workflow configuration or an older green run.

[CI](../.github/workflows/ci.yml) uploads the public tree/bundle and applicable
install/VSIX artifacts. Tagged release workflows publish binaries, crates, VSIX,
and the MCP listing. Successful local checks do not establish deployed state.

## Review interpretation

Explain whether a change affects source facts, response contracts, selection or
claim visibility, export-only metadata, or actual consumer behavior. Keep search
relevance separate from trust and synthesis separate from facts. Public mutation,
submission, and SLA promises require explicit contracts; do not add them through
release copy.
