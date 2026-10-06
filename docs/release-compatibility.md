# Release compatibility

Use documentation for the binary you installed. The latest stable release is
[`v1.0.3`](https://github.com/maxwellsantoro/dotrepo/releases/tag/v1.0.3), built from
the `codex/stable-1.0` maintenance line. The current `main` source identifies itself
as `2.0.0-alpha.0`; it includes unreleased public Rust API changes. Source merges
do not change an existing release bundle or installed crate.

## Version-matched documentation

For stable binaries, start with the tag's
[maintainer guide](https://github.com/maxwellsantoro/dotrepo/blob/v1.0.3/docs/maintainer-happy-path.md),
[trust model](https://github.com/maxwellsantoro/dotrepo/blob/v1.0.3/docs/trust-model.md),
and [MCP contract](https://github.com/maxwellsantoro/dotrepo/blob/v1.0.3/rfcs/0006-mcp-server-contract.md).
The tag's preparation documents retain their prepublication state. The current
[install guide](install.md) supplies published 1.0.3 pins, and the
[historical promotion backport](https://github.com/maxwellsantoro/dotrepo/blob/v1.0.2/docs/stable-promotion-backport.md)
retains the 1.0.2 patch scope. The [1.0.3 boundary contract](https://github.com/maxwellsantoro/dotrepo/blob/v1.0.3/CONTRIBUTING.md#path-containment-limits)
defines the added import protections. Installation and deployment receipts live in
[the dated 1.0.3 delivery evidence](../index/telemetry/stable-1.0.3-delivery-20261006/delivery.json).
The [1.0.2 receipt](../index/telemetry/command-semantics-20261004/delivery.json)
retains the preceding release and deployment observations unchanged.

Relative links in this checkout describe this branch unless stated otherwise.
Hosted JSON deploys independently of CLI/MCP releases: inspect live
[`meta.json`](https://dotrepo.org/v0/meta.json), record timestamps, and returned
fields rather than inferring server behavior from your client version.

## Safety-relevant differences

| Behavior | Stable `v1.0.3` | Unreleased `main` |
| --- | --- | --- |
| `promotion-report --apply` | Fails before writing records or evidence | Same no-write guard |
| Read-only promotion analysis | Uses manifest values and record-wide provenance; does not inspect upstream | Uses retained value- and timestamp-bound field assessments; still not fresh inspection |
| Make/Just commands | Conservative literal declarations; preserve wrapper entrypoints; withhold ambiguous or parameterized recipes | Same source-preserving extraction and consumer fallback checks |
| Non-running test examples | Withhold Go compilation/discovery, unresolved interpolation, and contribution examples requiring a directory change | Same classification plus newer execution-context contracts |
| Per-field evidence and execution contexts | No newer retained `fieldEvidence` or context schema | Exports matching retained assessments and validates exact-command contexts |
| MCP response sizes | JSON capped at 8 MiB, including streamed reads; bounded error bodies and diagnostics | Same caps |
| MCP lookup response | Summary, trust, metadata, optional query from compatibility routes | Also fetches profiles and follows validated immutable snapshot paths |
| MCP target checks | Default hosted-origin allowlist, HTTPS, common private/local checks, no redirects, address pinning | Adds IPv4-mapped IPv6, more non-public ranges/metadata hosts, and same-origin snapshot-path checks |
| Import text inputs | Existing discovery uses bounded regular files without symlinks; Unix descriptor-relative opens | Same reader, also used by newer manifest discovery |
| Rake commands | Withhold namespaces, conditional tasks and dynamic Ruby contexts | Same conservative root-task rule |
| Forced native import writes | Refuses symlinks, shared hardlinks and nonregular targets before writing | Same refusal contract |
| `dotrepo ci init` default | Retains prepublication `1.0.1`; pass `--version 1.0.3` explicitly | Pins `1.0.3`; no runtime latest-release discovery |

### Promotion and trust labels

Stable 1.0.2 and 1.0.3 disable standalone promotion writes. Read-only analysis retains the
older record-wide scoring model; a `verified` record does not prove that the newer
per-field checks ran. Review retained sources and record age for the fact needed.
Both maintenance patches preserve the stable schema and Rust API. Version
1.0.2 updated four external lock entries and the promotion/command safeguards;
1.0.3 adds bounded import reads, forced-write checks and conservative Rake
handling. Unix uses pinned directory descriptors; Windows ancestor replacement
and movement of the selected root retain documented best-effort limits.

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
[stable lookup policy](https://github.com/maxwellsantoro/dotrepo/blob/v1.0.3/crates/dotrepo-mcp/src/lookup.rs),
[stable handler](https://github.com/maxwellsantoro/dotrepo/blob/v1.0.3/crates/dotrepo-mcp/src/handlers.rs),
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
