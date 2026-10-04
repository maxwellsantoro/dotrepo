# Release compatibility

Use documentation for the binary you installed. The latest stable release is
[`v1.0.1`](https://github.com/maxwellsantoro/dotrepo/releases/tag/v1.0.1).
The current `main` source identifies itself as `2.0.0-alpha.0`; it is unreleased
development work, including public Rust API changes. A change merged on `main`
does not change an existing release bundle or installed crate. The
[`codex/stable-1.0` maintenance branch](https://github.com/maxwellsantoro/dotrepo/tree/codex/stable-1.0)
contains the merged 1.0.2 candidate; no 1.0.2 tag or artifacts have been published.

## Version-matched documentation

For stable binaries, start with the tag's
[installation guide](https://github.com/maxwellsantoro/dotrepo/blob/v1.0.1/docs/install.md),
[maintainer guide](https://github.com/maxwellsantoro/dotrepo/blob/v1.0.1/docs/maintainer-happy-path.md),
[trust model](https://github.com/maxwellsantoro/dotrepo/blob/v1.0.1/docs/trust-model.md),
and [MCP contract](https://github.com/maxwellsantoro/dotrepo/blob/v1.0.1/rfcs/0006-mcp-server-contract.md).
These are historical release documents; the caveats below explain where that
release's behavior differs from newer safeguards.

Relative documentation links in this checkout describe this branch unless a
section says otherwise. Check the tag and version when following those links.
Hosted JSON can be deployed independently of the CLI/MCP release: inspect the
live [`meta.json`](https://dotrepo.org/v0/meta.json), record timestamps, and
returned fields rather than inferring server behavior from your client version.

## Safety-relevant differences

| Behavior | Stable `v1.0.1` | Unreleased `main` |
| --- | --- | --- |
| `promotion-report --apply` | Can promote eligible index records and write `record.toml` and `evidence.md` | Fails without writing records or evidence |
| Standalone promotion analysis | Scores manifest values and record-wide provenance using heuristics; does not perform fresh upstream inspection | Reads retained field assessments tied to each value and check time; missing or invalidated assessments stay unresolved; still not fresh inspection |
| Per-field evidence | Does not implement the newer retained `fieldEvidence` export contract | Exports matching retained assessments; drops entries whose value or record check timestamp changed |
| MCP lookup response | Returns summary, trust, snapshot metadata, and optional query from compatibility routes | Also fetches a profile and uses the advertised immutable snapshot paths when valid |
| MCP target checks | Default hosted-origin allowlist, HTTPS requirement, common private/local address checks, redirects disabled, and resolved-address pinning | Adds checks for IPv4-mapped IPv6, more non-public ranges and metadata hostnames, and same-origin snapshot-path validation |
| `dotrepo ci init` default version | Uses the running binary's package version | Uses the stable version pinned in the source, currently `1.0.1`; does not query for a newer release |

### Promotion and trust labels

On stable, `promotion-report` without `--apply` is read-only. Adding `--apply`
can modify records and append evidence notes. Do not use that mode as proof of
fresh source verification. A record marked `verified` by that release is not
evidence that the newer per-field checks ran. Review the retained sources and
record age for the fact you need.

The development implementation disables this standalone write path entirely;
new promotion must go through crawler inspection and verification. The same
no-write guard is merged into the unreleased 1.0.2 maintenance source.
The [backport preparation record](https://github.com/maxwellsantoro/dotrepo/blob/codex/stable-1.0/docs/stable-promotion-backport.md)
defines its narrow scope: promotion apply is disabled, generated CI stays pinned
to published 1.0.1, and four dependency lock entries are updated. It does not
backport `main`'s field-evidence schema or newer MCP lookup behavior. Existing
1.0.1 installations retain the behavior in the table until a replacement ships.

Source comparison:
[stable CLI dispatch](https://github.com/maxwellsantoro/dotrepo/blob/v1.0.1/crates/dotrepo-cli/src/commands.rs),
[stable promotion implementation](https://github.com/maxwellsantoro/dotrepo/blob/v1.0.1/crates/dotrepo-core/src/promotion.rs),
[current promotion implementation](../crates/dotrepo-core/src/promotion.rs), and
[current no-write regression tests](../crates/dotrepo-core/tests/auto_publish.rs).

### MCP network policy

Stable lookup defaults to `https://dotrepo.org` and also permits
`https://dotrepo-org.workers.dev`. A different base requires
`DOTREPO_MCP_ALLOW_CUSTOM_BASE_URL=1`. The separate
`DOTREPO_MCP_UNSAFE_ALLOW_LOCAL_BASE_URL` override permits local/private targets
and HTTP for local development. Leave both overrides unset for ordinary hosted
lookup; they deliberately relax separate parts of the policy.
Using a custom local server requires both overrides, since the local override
does not remove the origin allowlist by itself.

The additional checks on `main` are defense in depth. This source comparison
establishes differences in validation, not a demonstrated exploit of the normal
allowlisted stable flow. In particular, the new snapshot-path guard protects a
snapshot-following flow that stable lookup does not use. Reachability of other
targets depends on configuration and inputs; do not describe all stable users as
exposed simply because a stricter guard exists on `main`.

Source comparison:
[stable lookup policy](https://github.com/maxwellsantoro/dotrepo/blob/v1.0.1/crates/dotrepo-mcp/src/lookup.rs),
[stable lookup handler](https://github.com/maxwellsantoro/dotrepo/blob/v1.0.1/crates/dotrepo-mcp/src/handlers.rs),
[current lookup policy](../crates/dotrepo-mcp/src/lookup.rs), and
[current lookup handler](../crates/dotrepo-mcp/src/handlers.rs).

## Installation and release checks

Use the [install guide](install.md) for pinned commands. The `v1.0.1` source has
`dotrepo-cli`, which supplies the `dotrepo` executable; the standalone `dotrepo`
alias package was added after that tag. Do not assume that the alias's current
README or development source describes the stable CLI package.

Before updating the stable recommendation, verify the published tag, binary and
crate versions, release assets, and the checks in this table. Keep unreleased
safeguards labeled until a release actually includes them. Record the release in
[the changelog](../CHANGELOG.md); documentation edits alone do not ship a fix.
