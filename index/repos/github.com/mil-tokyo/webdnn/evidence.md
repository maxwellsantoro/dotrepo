# Evidence

- Imported repository name and description from README.md.
- Left `repo.build` unset because `package.json` and `pyproject.toml` suggested conflicting build commands.
- Left `repo.test` unset because `package.json` and `pyproject.toml` suggested conflicting test commands.
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.build` to `npm run build` from `package.json` after deterministic escalation.
- Set `repo.test` to `npm run test:unit` from `.github/workflows/ci.yml` after deterministic escalation.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Downgrade guard

A prior verified status was preserved because no previously present field regressed in this refresh.
