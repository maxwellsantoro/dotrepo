# RC2 public delivery verification — October 29, 2026

This packet verifies the actual `v2.0.0-rc.2` preview against reviewed source
`94e02bd43d7cae1e5b6cd37ebd7a2a66a9b2b773`. Artifact availability, registry
publication, successful installation, and consumer benefit are separate claims.
Verification began only after the coordinator reported actual GitHub release and
MCP registry publication. Crate publication was still in progress at that point.

`verify_publication.py` reuses bounded helpers from the retained 1.0.3 publication
verifier without editing its historical bytes. The new controlled CLI checks
reuse its fixed extraction/read-boundary/promotion cases and add source-context
regressions and contained output-write refusals. These are own-project synthetic
fixtures; they do not execute arbitrary indexed repositories.

The bundle phase verifies the exact tag/source, GitHub asset digests and checksum
sidecars, MCPB manifest and embedded macOS/Linux MCP binary parity, and the exact
MCP registry version/asset hash. It then executes the macOS ARM CLI checks and
version-bound MCP/LSP stdio smoke from the tagged source. Linux asset and MCPB
hash agreement is not Linux execution.

The full phase additionally requires exact-version metadata for all seven public
crates, checksum agreement, clean `.cargo_vcs_info.json` source identity, and
byte comparisons of packaged Rust source/original manifests/READMEs against the
tag. Fresh isolated Cargo roots and a fresh target/cache install CLI, MCP, LSP
and the standalone alias with `--locked` and exact `=2.0.0-rc.2` selection. CLI
and alias refusal checks and registry MCP/LSP stdio then run locally on macOS.
No stable default, shared source, release tag, publication setting or installed
user tool is changed.

All downloads, clones, logs, installations and checkpoint receipts live beneath
new `/tmp/dotrepo-rc2-delivery-*` roots. Failures remain receipts; retrying uses a
new output root. Receipts preserve unresolved stages and observed workflow job
conclusions. A source build job is not an installed public binary test, and this
packet does not claim local Linux execution or independent consumer usefulness.

The full run passed on October 29 at `05:40:06 UTC`. The retained
[`delivery.json`](delivery.json) binds the receipt and verifier inputs;
[`receipts/attempt-03-full-pass/receipt.json`](receipts/attempt-03-full-pass/receipt.json)
contains the observed public identities, checksums, installation identities,
runtime versions, stage results and limitations. The release remains a preview:
the verified [GitHub release](https://github.com/maxwellsantoro/dotrepo/releases/tag/v2.0.0-rc.2)
is marked prerelease. The observed [publication workflow](https://github.com/maxwellsantoro/dotrepo/actions/runs/40823937226)
completed successfully, including crate and MCP registry publication.

| Observation | Result |
| --- | --- |
| Exact tag and all seven crates' clean VCS identity | Reviewed `94e02bd43d7cae1e5b6cd37ebd7a2a66a9b2b773` |
| Seven crate archive checksums and packaged source comparisons | Passed; Rust source, original manifests and mapped READMEs match the tag |
| Seven GitHub asset digests; tarball/MCPB checksum sidecars | Passed |
| MCPB embedded macOS and Linux MCP binaries | Byte-identical to the respective release tarballs |
| Exact MCP Registry version | Package URL and MCPB checksum agree |
| macOS ARM bundle CLI | All 40 controlled checks passed |
| Fresh exact-version locked registry CLI/MCP/LSP/alias installs | All four succeeded using a new Cargo home and target directory |
| Registry CLI and standalone alias CLI | All 40 controlled checks passed for each |
| Bundle and registry MCP/LSP | Four stdio smoke checks passed, including RC2 `serverInfo.version` assertions |

The CLI does not implement `--version`. Its version identity is bound to the
versioned bundle/tag or exact registry installation metadata; its own version
self-report remains unavailable. MCP and LSP report the expected server version.
The VSIX was verified as a release asset by digest and size; this packet did not
install it in an editor. No Linux binary was executed locally. The observed
publication workflow's Linux job builds artifacts; it does not establish a
fresh Linux public installation. Separate Linux execution receipts, if obtained,
belong to the coordinator's independent verification packet.

Two earlier bundle attempts are retained as failures, rather than overwritten:

- [`attempt-01-unsupported-cli-version`](receipts/attempt-01-unsupported-cli-version/receipt.json)
  incorrectly assumed the CLI exposed `--version`. The published CLI rejected
  that argument. The verifier now records the self-report limitation and checks
  the supported help surface and artifact/installation identity.
- [`attempt-02-optional-fixture-key`](receipts/attempt-02-optional-fixture-key/receipt.json)
  stopped in the check harness because a frozen expectation omitted an optional
  scalar key. The corrected harness reads absent optional scalar values as
  absent. Its unchanged candidate/context comparisons then passed in the full
  run. The failed harness log is retained alongside its receipt.

These failures do not show an artifact checksum mismatch or an installed safety
regression. They remain limits on the earlier attempted verification. The final
successful receipt covers the corrected scripts, whose hashes are retained in
`delivery.json` and `evidence-manifest.json`. Raw public metadata, checksum
sidecars, controlled check results and stage logs are retained here; large
downloads, source clone and installations remain in the receipt's temporary
output root.

Focused checks: both scripts pass Ruff lint and formatting; the full artifact
verification exits successfully; the retained binding/hash check confirms all
seven crate identities, four installations, eleven successful stages and three
sets of 40 controlled checks. These results establish bounded release delivery
and local behavior, without establishing independent agent benefit.
