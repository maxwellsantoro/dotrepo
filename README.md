# dotrepo

[![CI](https://github.com/maxwellsantoro/dotrepo/actions/workflows/ci.yml/badge.svg)](https://github.com/maxwellsantoro/dotrepo/actions/workflows/ci.yml)
[![Latest Release](https://img.shields.io/github/v/release/maxwellsantoro/dotrepo)](https://github.com/maxwellsantoro/dotrepo/releases/latest)
[![License: MIT](https://img.shields.io/badge/license-MIT-0f766e.svg)](LICENSE)

**Look up a repository's purpose, build and test commands, docs, and owners.**

dotrepo is an open repository metadata protocol with a reference toolchain and
public index. It gives agents and tools those facts as JSON, through MCP, or from a local
`.repo` file. Each record includes source and trust context so you can decide
whether to use an answer or inspect upstream.

## Try it: orient yourself in ripgrep

Fetch the indexed profile without installing anything or cloning the repository:

```bash
curl -sS https://dotrepo.org/v0/repos/github.com/BurntSushi/ripgrep/profile.json
```

The response groups purpose, execution, documentation, and ownership. Check
`record.generatedAt`, `record.freshnessStatus`, conflicts, and the fields your
task needs. `freshness.generatedAt` dates the export, not the source facts.
A missing, old, or conflicting answer needs an upstream check. Returned commands
are data to review, not permission to execute them.

## Connect your agent

Install the stable MCP server with a Rust toolchain, or use the
[stable release bundle](https://github.com/maxwellsantoro/dotrepo/releases/tag/v1.0.2):

```bash
cargo install dotrepo-mcp --version 1.0.2 --locked
```

For clients that use an `mcpServers` configuration:

```json
{
  "mcpServers": {
    "dotrepo": { "command": "dotrepo-mcp", "args": [] }
  }
}
```

Ask the client to call `dotrepo.lookup` with these arguments:

```json
{
  "repositoryUrl": "https://github.com/BurntSushi/ripgrep",
  "path": "repo.test"
}
```

See [installation](docs/install.md) for the CLI, LSP, and VS Code extension, and
[consumer integration](docs/external-consumer-integration.md) for fallback rules
and a runnable client.

**Version matters:** the stable release is `v1.0.2`; this branch is unreleased
`2.0.0-alpha.0`. Stable includes the bounded command-extraction fixes, the
promotion no-write guard, and response-size caps. The newer field-evidence
schema, execution contexts, and additional MCP target checks remain on `main`.
Use the
[version comparison and stable documentation](docs/release-compatibility.md).

## What you can use it for

- **Repository orientation:** get purpose, docs, owners, and reported commands
  before deciding what source files to inspect
- **Agent integrations:** make a first lookup, retain trust and age, then fall
  back to upstream when the answer does not meet your task's needs
- **Maintainer metadata:** keep a native `.repo` file and supported documentation
  blocks consistent with validation and generated-surface checks
- **Repository discovery:** search, compare factual profiles, and traverse
  repository relationships through the [public API](docs/public-export-examples.md)

Indexed overlays are generated from public source material, so maintainers do
not need to adopt dotrepo for their repository to appear. A native `.repo`
provides maintainer control. Routine generated records are machine-checked;
`verified` does not mean human-reviewed or correct in every field.

## Add a record to your repository

Install the stable CLI from the release bundle or with
`cargo install dotrepo-cli --version 1.0.2 --locked`, then:

```bash
# Start from existing README.md, CODEOWNERS, and SECURITY.md:
dotrepo --root <repo> import
# Review the generated .repo, then:
dotrepo --root <repo> validate
dotrepo --root <repo> query repo.build --raw
dotrepo --root <repo> trust
dotrepo --root <repo> generate --check
```

Use `init` instead of `import` to start from a blank scaffold. The
[stable maintainer guide](https://github.com/maxwellsantoro/dotrepo/blob/v1.0.2/docs/maintainer-happy-path.md)
walks through adoption; [sync boundaries](docs/sync-boundaries.md) explain which
files and regions dotrepo can manage.

## Limits and evidence

- Metadata supports orientation. Architecture research, suitability decisions,
  debugging, and code changes still require source inspection
- Coverage, correctness, completeness, and freshness are separate. Records can
  be incomplete, stale, or wrong even when marked `verified`; retained
  field-level evidence is available only where the producing version and crawl
  saved it. See the [trust model](docs/trust-model.md)
- The [measurement page](https://dotrepo.org/efficiency/) reports field presence
  and modeled requests. Those are not accuracy or measured end-to-end agent
  savings
- The [head-to-head benchmark](benchmarks/head-to-head/) keeps wins and losses
  against a GitHub API + README baseline. Fixing its examples is regression
  evidence, not proof of generalization
- Sustained independent consumer adoption remains an open success criterion.
  In-repository clients and AI interviews do not establish external demand

## Read next

- [Documentation map](docs/README.md) and [release compatibility](docs/release-compatibility.md)
- [Toolchain and protocol reference](docs/reference-overview.md), including MCP
  tools, validation scope, and version boundaries
- [Hosted API examples](docs/public-export-examples.md), [public architecture](docs/public-surface.md),
  and [own-project study and later pilot](docs/consumer-pilot.md)
- [Trust model](docs/trust-model.md) and [authority rules](rfcs/0004-index-and-trust-model.md)
- [Roadmap](ROADMAP.md), [contributing](CONTRIBUTING.md), and [index operations](index/README.md)

For implementation, start with the [roadmap packets](ROADMAP.md#active-execution-order)
and [team execution guide](docs/agent-execution.md). [Repository guidance](AGENTS.md)
owns contracts; generated reports and dated archives own outcome evidence.

Repository Python tooling uses `uv`: run `uv venv`, `uv sync --dev --locked`,
then invoke scripts and tests through `uv run`.
