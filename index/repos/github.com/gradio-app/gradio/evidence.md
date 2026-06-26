# Evidence

- Imported repository name and docs entry points from README.md.
- Imported the security reporting channel from SECURITY.md.
- Inferred fallback values for `repo.description` because the imported files did not provide enough structured metadata.
- Left `repo.build` unset because `package.json` and `pyproject.toml` suggested conflicting build commands.
- Left `repo.test` unset because `package.json` and `pyproject.toml` suggested conflicting test commands.
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.build` to `pnpm build` from `package.json` after deterministic escalation.
- Left `repo.test` unset after model escalation: The candidates represent mutually exclusive technology stacks (Node.js/pnpm vs Python/pytest); no single primary value can represent the repository..
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Filled repo.description from GitHub repository metadata when the README surface did not provide one.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
