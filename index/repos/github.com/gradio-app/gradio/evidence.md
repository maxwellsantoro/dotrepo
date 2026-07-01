# Evidence

- Imported repository name and docs entry points from README.md.
- Imported the security reporting channel from SECURITY.md.
- Inferred fallback values for `repo.description` because the imported files did not provide enough structured metadata.
- Left `repo.build` unset because `package.json` and `pyproject.toml` suggested conflicting build commands.
- Left `repo.test` unset because `package.json` and `pyproject.toml` suggested conflicting test commands.
- Discovered related relation to github.com/gradio-app/gradio from README cross-link.
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.test` to `PERF_RESULTS_FILE=/tmp/bench_base.json pnpm exec playwright test \` from `.github/workflows/frontend_profiling.yml` after deterministic escalation.
- Set `repo.build` to `pnpm build` from `package.json` after model escalation.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Filled repo.description from GitHub repository metadata when the README surface did not provide one.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Downgrade guard

A prior verified status was preserved because no previously present field regressed in this refresh.
