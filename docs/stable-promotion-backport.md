# Stable promotion guard candidate

This checkout prepares a 1.0.2 patch from immutable tag `v1.0.1` for local
validation. It is not a published release and must not replace install defaults
until the artifacts ship.

`promotion-report --apply` previously changed eligible retained records to
`verified` and appended verification-like evidence without inspecting upstream.
It now fails before filesystem access and directs the caller to fresh crawler
verification. The public function signature and report types remain available;
read-only analysis still uses the stable heuristic and does not prove fresh
verification. This backport does not change crawler scoring, schema fields,
public JSON contracts, or the stable Rust data types.

The default generated maintainer CI remains pinned to published 1.0.1, separately
from this candidate's package version. Checkout is SHA-pinned. The native example
is aligned with that default; the original tag had an existing test failure
because the generator emitted 1.0.1 while the example used 1.0.0.

Validate with the repository's locked workspace and Python tests, the CLI CI
contract test, and the no-write regression in `tests/auto_publish.rs`. Compare
all non-dotrepo Cargo lock entries against the immutable tag. Package and smoke
test the CLI, public-query, MCP, and LSP binaries before publication. Retain the
baseline failure and candidate results in the release preparation report.

All other behavior follows the 1.0.1 source. Current `main` documentation and
development-only safeguards do not apply to this candidate. Release publication,
cross-platform artifacts, and install-default promotion remain release work.

The immutable dependency audit identified seven advisories. The candidate updates
four compatible lock entries: anyhow 1.0.103 ([RUSTSEC-2026-0190](https://rustsec.org/advisories/RUSTSEC-2026-0190)),
crossbeam-epoch 0.9.20 ([RUSTSEC-2026-0204](https://rustsec.org/advisories/RUSTSEC-2026-0204)),
rustls 0.23.45 ([RUSTSEC-2026-0285](https://rustsec.org/advisories/RUSTSEC-2026-0285)),
and rustls-webpki 0.103.14 ([RUSTSEC-2026-0104](https://rustsec.org/advisories/RUSTSEC-2026-0104),
also covering 0049, 0098, and 0099). Other external lock entries must remain
unchanged. An equivalent boolean-expression cleanup in escalation accommodates
strict Clippy on the current toolchain without changing routing behavior.

The release workflow retains its stable packaging jobs while SHA-pinning all
third-party actions, declaring the pinned Rust action's toolchain explicitly,
and using locked binary builds. Cross-platform execution still requires CI.
The release gate's Python subprocesses use `uv run python`, matching the current
repository tooling convention; its command-prefix contract is updated accordingly.
