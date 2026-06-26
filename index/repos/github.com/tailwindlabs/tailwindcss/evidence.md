# Evidence

- Imported repository name and description from README.md.
- Imported maintainer candidates from CODEOWNERS.
- Left `repo.build` unset because `Cargo.toml` and `package.json` suggested conflicting build commands.
- Left `repo.test` unset because `Cargo.toml` and `package.json` suggested conflicting test commands.
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.test` to `npm run test:ui` from `.github/workflows/ci.yml` after deterministic escalation.
- Left `repo.build` unset after model escalation: The repository contains both a Rust workspace and a Node.js package, representing two distinct primary build systems with no indication of which is the primary repository purpose..
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
