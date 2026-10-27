# Evidence

- Imported repository name and docs entry points from README.md.
- Imported the security reporting channel from SECURITY.md.
- Inferred repo.build from pyproject.toml as `python -m build`.
- Inferred repo.test from pyproject.toml as `python -m pytest`.
- Imported repo.toolchain.min from pyproject.toml as `3.12` (Python).
- Imported docs.root as `./docs/configuration.md`. Explicit documentation link at README.md:88: | [Configuration](./docs/configuration.md)             | Sandbox, agent mode, tool approval, full `config.yaml` example                           |
- Imported docs.getting_started as `./docs/installation.md`. Explicit documentation link at README.md:55: These steps get you running on macOS or Windows (WSL). Need more detail or a different platform? See the [Installation Guide](./docs/installation.md).
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.name` to `magentic-ui` from `GitHub API` after deterministic escalation.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
