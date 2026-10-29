# RC2 publication evidence join — October 29, 2026

`v2.0.0-rc.2` identifies reviewed source
`94e02bd43d7cae1e5b6cd37ebd7a2a66a9b2b773`. The source-preparation PR's
full CI, the exact release commit's post-merge CI, and the tag publication
workflow are retained as separate GitHub API observations. The publication
workflow passed all seven jobs, including crate and MCP registry publication.
The release is a preview; stable production guidance remains `1.0.4`.

The [macOS delivery packet](../rc2-delivery-20261029/README.md) binds actual
assets, all seven crates, clean source provenance, MCPB/registry agreement and
fresh locked CLI/MCP/LSP/alias installations. Its controlled checks execute
locally on macOS ARM64. The [Linux packet](../rc2-linux-verification-20261029/README.md)
records separate Linux ARM64 container execution on the macOS host; it cannot
establish native Linux-host or x86_64 bundle execution. Each packet retains its
own environment, scripts, raw results, failed attempts and limitations.

`publication.json` joins their manifest hashes and the API observations without
modifying either frozen packet. The independent macOS review checked existing
archive/source/binary/log bindings; it did not repeat network access or installs.
The macOS packet did not retain pre-tag CI, so the coordinator captured it here
instead of inferring CI success from successful publication.

The exact release excludes the subsequent E1 extraction and F-05 experiment
changes in [PR #180](https://github.com/maxwellsantoro/dotrepo/pull/180). Its
merged-tree CI also passed, separately from this release. Documentation changes
after publication do not replace the immutable tag, packaged READMEs or RC1
artifacts. The CLI has no version self-report flag; artifact and installation
provenance bind its identity. MCP/LSP initialization reports the release version.
VSIX asset integrity was checked; editor installation was not tested.

These observations establish bounded release delivery and installed behavior.
They do not establish instruction applicability on unfamiliar tasks, consumer
benefit, independent adoption or a sustained scheduled-operation window.
