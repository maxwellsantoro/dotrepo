# Evidence

- Imported repository name and docs entry points from README.md.
- Imported maintainer candidates from CODEOWNERS. Maintainer information was imported from broad CODEOWNERS patterns; `owners.team` prefers `@Stirling-Tools/maintainers` from the repo-wide rule, and `owners.maintainers` preserves narrower owner candidates.
- Imported the security reporting channel from SECURITY.md.
- Ignored component-scoped commands from `engine/pyproject.toml` as repository defaults.
- Inferred repo.build from build.gradle as `./gradlew build`.
- Inferred repo.test from build.gradle as `./gradlew test`.
- Imported repo.toolchain.min from engine/pyproject.toml as `3.13` (Python).
- Imported docs.root as `https://docs.stirlingpdf.com`. Explicit documentation link at README.md:49: - [**Documentation**](https://docs.stirlingpdf.com)
- Discovered related relation to github.com/Stirling-Tools/Stirling-PDF from README cross-link.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
