# Evidence

- Imported repository name and docs entry points from README.md.
- Imported maintainer candidates from CODEOWNERS.
- Imported the security reporting channel from SECURITY.md.
- Inferred fallback values for `repo.description` because the imported files did not provide enough structured metadata.
- Ignored component-scoped commands from `superset-frontend/packages/generator-superset/package.json` as repository defaults.
- Inferred repo.build from pyproject.toml as `python -m build`.
- Inferred repo.test from pyproject.toml as `python -m pytest`.
- Imported repo.toolchain.min from pyproject.toml as `3.11` (Python).
- Imported docs.root as `https://superset.apache.org/user-docs/`. Explicit documentation link at README.md:55: - **[User Guide](https://superset.apache.org/user-docs/)** — For analysts and business users. Explore data, build charts, create dashboards, and connect databases.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
