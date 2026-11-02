# Evidence

- Imported repository name from README.md.
- Left `repo.build` unset because Go workflow component scope is unresolved in `.github/workflows/build.yml`; a conventional root module command cannot establish repository coverage.
- Left `repo.test` unset because Go workflow component scope is unresolved in `.github/workflows/build.yml`; a conventional root module command cannot establish repository coverage.
- Imported repo.toolchain.min from go.mod as `1.20` (Go).
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
