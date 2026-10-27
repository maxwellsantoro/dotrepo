# Evidence

- Imported repository name and docs entry points from README.md.
- Imported the security reporting channel from SECURITY.md.
- Imported repo.build from package.json as `pnpm build`.
- Left `repo.test` unset because `package.json` and `pyproject.toml` suggested conflicting test commands.
- Imported repo.toolchain.min from pyproject.toml as `3.10` (Python).
- Imported docs.root as `https://gradio.app/docs/`. Explicit documentation link at README.md:23: | [Documentation](https://gradio.app/docs/)
- Imported docs.getting_started as `https://gradio.app/getting_started/`. Explicit documentation link at README.md:25: | [Getting Started](https://gradio.app/getting_started/)
- Discovered related relation to github.com/gradio-app/gradio from README cross-link.
- This is an overlay record, not a maintainer-controlled canonical record.

- Left `repo.test` unset after deterministic escalation: conflicting test candidates from package.json, pyproject.toml. Preserved 2 candidate command(s) in `repo.test_candidates` instead of discarding them.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
