# Evidence

- Imported repository name, description, and docs entry points from README.md.
- Left `repo.build` unset because `.github/workflows/build-release-apk.yml` and `.github/workflows/ci.yml` suggested conflicting build commands.
- Left `repo.test` unset because `.github/workflows/build-release-apk.yml` and `.github/workflows/ci.yml` suggested conflicting test commands.
- This is an overlay record, not a maintainer-controlled canonical record.

- Left `repo.build` unset after deterministic escalation: no unique build/test candidate after deterministic tier walk.
- Left `repo.test` unset after deterministic escalation: no unique build/test candidate after deterministic tier walk.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
