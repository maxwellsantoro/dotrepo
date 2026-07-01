# Evidence

- No README.md, CODEOWNERS, or SECURITY.md content was imported; this record needs manual completion.
- Inferred fallback values for `repo.name` and `repo.description` because the imported files did not provide enough structured metadata.
- Left `repo.build` unset because `Cargo.toml` and `package.json` suggested conflicting build commands.
- Left `repo.test` unset because `Cargo.toml` and `package.json` suggested conflicting test commands.
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.build` to `pnpm run build` from `.github/workflows/build_and_deploy.yml` after deterministic escalation.
- Left `repo.test` unset after model escalation: The repository contains multiple distinct manifest files (Cargo.toml and package.json) indicating a polyglot repository with no single primary test command.. Preserved 2 candidate command(s) in `repo.test_candidates` instead of discarding them.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Filled repo.description from GitHub repository metadata when the README surface did not provide one.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Downgrade guard

Status dropped from a prior verified record because the following previously present field(s) regressed: repo.test.
