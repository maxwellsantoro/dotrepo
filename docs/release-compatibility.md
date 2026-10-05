# Release compatibility

Use documentation for the binary you installed. The latest stable release is
[`v1.0.2`](https://github.com/maxwellsantoro/dotrepo/releases/tag/v1.0.2), built from
the `codex/stable-1.0` maintenance line. The current `main` source identifies itself
as `2.0.0-alpha.0`; it includes unreleased public Rust API changes. Source merges
do not change an existing release bundle or installed crate.

## Version-matched documentation

For stable binaries, start with the tag's
[maintainer guide](https://github.com/maxwellsantoro/dotrepo/blob/v1.0.2/docs/maintainer-happy-path.md),
[trust model](https://github.com/maxwellsantoro/dotrepo/blob/v1.0.2/docs/trust-model.md),
and [MCP contract](https://github.com/maxwellsantoro/dotrepo/blob/v1.0.2/rfcs/0006-mcp-server-contract.md).
The tag's preparation documents retain their prepublication state. The current
[install guide](install.md) supplies published 1.0.2 pins, and the
[backport record](https://github.com/maxwellsantoro/dotrepo/blob/v1.0.2/docs/stable-promotion-backport.md)
defines the stable patch scope. Installation and deployment receipts live in
[the dated delivery evidence](../index/telemetry/command-semantics-20261004/delivery.json).

Relative links in this checkout describe this branch unless stated otherwise.
Hosted JSON deploys independently of CLI/MCP releases: inspect live
[`meta.json`](https://dotrepo.org/v0/meta.json), record timestamps, and returned
fields rather than inferring server behavior from your client version.

## Safety-relevant differences

| Behavior | Stable `v1.0.2` | Unreleased `main` |
| --- | --- | --- |
| `promotion-report --apply` | Fails before writing records or evidence | Same no-write guard |
| Read-only promotion analysis | Uses manifest values and record-wide provenance; does not inspect upstream | Uses retained value- and timestamp-bound field assessments; still not fresh inspection |
| Make/Just commands | Conservative literal declarations; preserve wrapper entrypoints; withhold ambiguous or parameterized recipes | Same source-preserving extraction and consumer fallback checks |
| Non-running test examples | Withhold Go compilation/discovery, unresolved interpolation, and contribution examples requiring a directory change | Same classification plus newer execution-context contracts |
| Per-field evidence and execution contexts | No newer retained `fieldEvidence` or context schema | Exports matching retained assessments and validates exact-command contexts |
| MCP response sizes | JSON capped at 8 MiB, including streamed reads; bounded error bodies and diagnostics | Same caps |
| MCP lookup response | Summary, trust, metadata, optional query from compatibility routes | Also fetches profiles and follows validated immutable snapshot paths |
| MCP target checks | Default hosted-origin allowlist, HTTPS, common private/local checks, no redirects, address pinning | Adds IPv4-mapped IPv6, more non-public ranges/metadata hosts, and same-origin snapshot-path checks |
| Forced native import writes | Earlier path-containment behavior | Adds symlink and shared-hardlink overwrite refusal |
| `dotrepo ci init` default | Retains prepublication `1.0.1`; pass `--version 1.0.2` explicitly | Pins `1.0.2`; no runtime latest-release discovery |

### Promotion and trust labels

Stable 1.0.2 disables standalone promotion writes. Read-only analysis retains the
older record-wide scoring model; a `verified` record does not prove that the newer
per-field checks ran. Review retained sources and record age for the fact needed.
The patch preserves the stable schema and Rust API, while updating four external
lock entries and the bounded safety behaviors above.

Historical 1.0.1 allowed `promotion-report --apply` to modify records and append
evidence. Updating documentation does not change those already-installed binaries
or retroactively recheck older records. New verification on `main` goes through
inspection and verification; retained assessment analysis is not fresh inspection.

Source comparison:
[1.0.1 promotion](https://github.com/maxwellsantoro/dotrepo/blob/v1.0.1/crates/dotrepo-core/src/promotion.rs),
[1.0.2 CLI dispatch](https://github.com/maxwellsantoro/dotrepo/blob/v1.0.2/crates/dotrepo-cli/src/commands.rs),
[current promotion](../crates/dotrepo-core/src/promotion.rs), and
[current regression tests](../crates/dotrepo-core/tests/auto_publish.rs).

### MCP network policy

Stable lookup defaults to `https://dotrepo.org` and also permits
`https://dotrepo-org.workers.dev`. A different base requires
`DOTREPO_MCP_ALLOW_CUSTOM_BASE_URL=1`. The separate
`DOTREPO_MCP_UNSAFE_ALLOW_LOCAL_BASE_URL` override permits local/private targets
and HTTP for local development. A custom local server needs both overrides.
Leave both unset for ordinary hosted lookup.

Additional target checks on `main` are defense in depth. This source comparison
establishes validation differences, not a demonstrated exploit of the normal
allowlisted stable flow. The snapshot-path guard protects a flow stable lookup
does not use. Reachability of other targets depends on configuration and inputs.

Source comparison:
[stable lookup policy](https://github.com/maxwellsantoro/dotrepo/blob/v1.0.2/crates/dotrepo-mcp/src/lookup.rs),
[stable handler](https://github.com/maxwellsantoro/dotrepo/blob/v1.0.2/crates/dotrepo-mcp/src/handlers.rs),
[current lookup policy](../crates/dotrepo-mcp/src/lookup.rs), and
[current handler](../crates/dotrepo-mcp/src/handlers.rs).

## Installation and release checks

Use the [install guide](install.md) for pinned commands. Stable publishes six
workspace crates, including `dotrepo-cli`, which supplies `dotrepo` and
`dotrepo-public-query`. The standalone `dotrepo` alias on `main` is absent from
this maintenance release.

Before changing stable recommendations, verify tag/package parity, assets,
checksums, actual installation, and the relevant safety fixtures. Keep unreleased
safeguards labeled. Record completed publication in [the changelog](../CHANGELOG.md);
policy acceptance and successful installation do not establish independent task
correctness or consumer adoption.
