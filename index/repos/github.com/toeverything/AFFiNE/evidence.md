# Evidence

- Imported repository name, description, and docs entry points from README.md.
- Imported maintainer candidates from CODEOWNERS. Maintainer information was imported from CODEOWNERS; `owners.team` is `@toeverything/blocksuite-core` because it is the clearest imported team signal, but `owners.maintainers` still preserves narrower owner candidates.
- Imported the security reporting channel from SECURITY.md.
- Left `repo.build` unset because `Cargo.toml` and `package.json` suggested conflicting build commands.
- Left `repo.test` unset because `Cargo.toml` and `package.json` suggested conflicting test commands.
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.test` to `yarn affine @affine/server test:copilot:coverage --forbid-only` from `.github/workflows/copilot-test.yml` after deterministic escalation.
- Left `repo.build` unset after deterministic escalation: no unique build/test candidate after deterministic tier walk.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
