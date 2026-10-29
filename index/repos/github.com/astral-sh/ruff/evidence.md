# Evidence

- Imported repository name and docs entry points from README.md.
- Imported maintainer candidates from CODEOWNERS. Maintainer information was imported from broad CODEOWNERS patterns with multiple team owners, so `owners.team` was left unset and `owners.maintainers` preserves the competing owner candidates.
- Ignored component-scoped commands from `playground/ruff/package.json` as repository defaults.
- Withheld `repo.test` from `CONTRIBUTING.md` because its Cargo selector describes a component, not the repository default.
- Inferred repo.build from Cargo.toml as `cargo build --workspace`.
- Left `repo.test` unset because `Cargo.toml` and `pyproject.toml` suggested conflicting test commands.
- Imported repo.toolchain.min from Cargo.toml as `1.97` (Rust).
- Imported docs.root as `https://docs.astral.sh/ruff/`. Explicit documentation link at README.md:12: [**Docs**](https://docs.astral.sh/ruff/) | [**Playground**](https://play.ruff.rs/)
- Discovered related relation to github.com/astral-sh/ruff from README cross-link.
- This is an overlay record, not a maintainer-controlled canonical record.

- Left `repo.test` unset after deterministic escalation: no unique build/test candidate after deterministic tier walk. Preserved 2 candidate command(s) in `repo.test_candidates` instead of discarding them.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
