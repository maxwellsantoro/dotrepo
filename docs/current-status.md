# Current status

As of March 9, 2026, dotrepo is a coherent early implementation of the protocol,
reference toolchain, and seed index. It is still not production-hardened, but it
is no longer just an architecture sketch.

## What exists now

- A canonical root `.repo` format plus overlay records for index use
- Shared Rust core semantics for validation, query, trust, import, generate-check,
  and authority/conflict reporting
- A thin CLI, stdio MCP server, stdio LSP server, and first VS Code extension shell
- Managed sync for supported Markdown surfaces through explicit managed regions
- Richer import heuristics for `README.md`, `CODEOWNERS`, and `SECURITY.md`, backed
  by a checked-in fixture pack and regression gate
- A seed `index/` tree with evidence rules, showcase overlays, and validation checks
- Contract-level claim, supersede, and conflict surfacing semantics

## What dotrepo does not promise yet

- Production hardening, broad ecosystem adoption, or long-tail operational polish
- A full maintainer claim workflow product surface
- A public index site or query API
- Bundle mode or first-class workspace/relations support
- Arbitrary prose round-tripping or automatic conversion of unmanaged files into
  managed-region files
- Editor assistance for placing managed-region markers or semantic autofix flows
- Full TOML language-server parity beyond the current schema-shaped manifest surface

## What is true about the current editor and sync layers

- The editor layer is intentionally thin. The LSP and VS Code extension reuse core
  validation and trust semantics rather than inventing a second truth model.
- Managed sync is intentionally narrow. dotrepo preserves user-authored prose
  outside supported managed regions, and malformed or unsupported layouts fail
  explicitly instead of being guessed through.
- The current sync contract is limited to supported Markdown surfaces. `CODEOWNERS`
  can be generated, but it is not part of the managed-region contract.

## What the next strategic constraint is

The next meaningful constraint is no longer import quality or initial editor
ergonomics. It is maintainer authority handoff at the product and index level:
how maintainers claim representation, how overlays transition cleanly to canonical
records, and how conflict visibility remains trustworthy as adoption grows.

That is why the next strategic track should focus on maintainer claim workflow and
index-side handoff, not on widening the editor surface further.
