# DotRepo CLI

Inspect and maintain repository metadata with the `dotrepo` command. Records
retain evidence, trust and freshness context. Inspect upstream when a record is
missing, stale, conflicting or insufficient for your task. This package also
supplies the `dotrepo-public-query` server.

For production, install the verified stable package:

```bash
cargo install dotrepo-cli --version 1.0.4 --locked
```

After installation:

```bash
dotrepo --help
dotrepo --root . validate
dotrepo --root . query repo.build
```

[Installation and release channels](https://github.com/maxwellsantoro/dotrepo/blob/main/docs/install.md) explain stable 1.0.4 and the 2.0 release candidate. The registry may show the RC as latest; choose stable explicitly for production.

[Protocol and project](https://github.com/maxwellsantoro/dotrepo) · [Public repository lookup](https://dotrepo.org/)
