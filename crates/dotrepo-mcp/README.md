# dotrepo MCP server

Expose repository facts, trust, import and validation through a stdio Model Context Protocol server.

For production, install the verified stable package:

```bash
cargo install dotrepo-mcp --version 1.0.4 --locked
```

After installation:

```bash
dotrepo-mcp
```

Configure your MCP client (the surrounding configuration varies by client):

```json
{"mcpServers":{"dotrepo":{"command":"dotrepo-mcp","args":[]}}}
```

The server uses stdio; it does not start an HTTP listener.

[Installation and release channels](https://github.com/maxwellsantoro/dotrepo/blob/main/docs/install.md) explain stable 1.0.4 and the 2.0 release candidate. The registry may show the RC as latest; choose stable explicitly for production.

[Protocol and project](https://github.com/maxwellsantoro/dotrepo) · [Public repository lookup](https://dotrepo.org/)
