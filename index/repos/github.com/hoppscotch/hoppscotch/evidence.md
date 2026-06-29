# Evidence

- Imported repository name, description, and docs entry points from README.md.
- Imported maintainer candidates from CODEOWNERS.
- Imported the security reporting channel from SECURITY.md.
- Left `repo.build` unset because `.github/workflows/build-hoppscotch-agent.yml` and `.github/workflows/build-hoppscotch-desktop.yml` suggested conflicting build commands.
- Imported repo.test from package.json as `pnpm test`.
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.build` to `pnpm tauri build --verbose --target x86_64-apple-darwin` from `.github/workflows/build-hoppscotch-agent.yml` after deterministic escalation.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
