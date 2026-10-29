# RC2 Linux ARM64 registry verification

This packet records actual Linux ARM64 container execution on a macOS ARM64 host.
It does not establish native Linux host behavior or execute the x86_64 release
bundle. The exact official cached Rust image is
`sha256:114c7a4425406451c2866b6aafe69fe29b1b298832db1277d411ac73c82d04d6`.

`preparation.json` preserves the initial plan, source archive identity and selected
controls. `image-inspect.json` and `docker-server.json` preserve image/engine
identity. The source archive contains only dotrepo-owned fixtures and examples at
tag `v2.0.0-rc.2`, commit
`94e02bd43d7cae1e5b6cd37ebd7a2a66a9b2b773`.

The initial root-directory attempt failed because its tmpfs mounts omitted
explicit `exec`: Cargo could not execute a dependency build script. That verifier
configuration failure, raw logs, container inspect and removal receipt remain
preserved. It is not classified as a package defect. `attempt-2/` starts again
with a new container and empty Cargo home, using explicit `exec` tmpfs mounts.

The containers have no host mounts, Docker socket, forwarded credentials or host
environment. They run UID/GID 1000 with a read-only root, all capabilities dropped,
no-new-privileges, bounded memory/CPU/processes and writable temporary filesystems.
Public network access is available during registry installation and is
disconnected before the controlled binary checks. Network access during installs
is Docker bridge access rather than a domain-enforcing proxy. Container inspect
and actual environment are retained. No arbitrary upstream project commands or
model calls are executed.

Each package is installed from the public registry with:

```text
cargo install PACKAGE --locked --version =2.0.0-rc.2 \
  --root /work/install-PACKAGE --target-dir /work/cargo-target
```

The four packages are `dotrepo-cli`, `dotrepo-mcp`, `dotrepo-lsp` and the standalone
`dotrepo` alias. Within the fresh second container they share the Cargo download
and build cache sequentially. Host/VM filesystem caches are uncontrolled. Exact
crate metadata, downloaded crate checksums, clean packaged source commit,
`.crates2.json`, install logs, compiler and kernel observations establish version
and provenance. The CLI has no `--version` option; it is not used as a verifier.

Run the host orchestration through uv, from the repository checkout:

```text
uv run python index/telemetry/rc2-linux-verification-20261029/attempt-2/install_linux.py
uv run python index/telemetry/rc2-linux-verification-20261029/attempt-2/check_linux.py
```

These scripts intentionally refuse to overwrite retained receipts. A reproduction
must copy them and `controlled-source.tar` into a new evidence directory, alongside
the parent `preparation.json`, then use a new container. All Python runs on the
host via uv; the image does not need Python or uv.

The checks cover 25 source-owned extraction fixtures, nine input/write boundaries,
five generation/init output boundaries and the removed promotion write option.
Missing optional expected scalar command keys are interpreted as absent using
`.get()`, matching fixture semantics. Fixture command text is never executed.
Additional controls inspect five installed ELF headers for AArch64, retain binary
hashes/help, validate through the standalone alias, and exercise actual MCP
newline JSON and LSP Content-Length stdio initialization and tool/diagnostic
behavior. Raw request bytes, stdout, stderr and command receipts are retained.

The successful attempt's `installation-complete.json`, `safety-results.json` and
`controls-complete.json` are the result owners. Their absence means that stage did
not finish. The final `verification.json` and `artifact-hashes.json` bind the
retained result and cleanup evidence. These are bounded packaging/safety controls,
not extraction qualification on unfamiliar upstream projects or consumer benefit
evidence.
