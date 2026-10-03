# Evidence

- Imported repository name and docs entry points from README.md.
- Imported maintainer candidates from CODEOWNERS. Maintainer information was imported from broad CODEOWNERS patterns; `owners.team` prefers `@Stirling-Tools/maintainers` from the repo-wide rule, and `owners.maintainers` preserves narrower owner candidates.
- Imported the security reporting channel from SECURITY.md.
- Left `repo.build` unset because `engine/pyproject.toml` and `build.gradle` suggested conflicting build commands.
- Left `repo.test` unset because `engine/pyproject.toml` and `build.gradle` suggested conflicting test commands.
- Imported repo.toolchain.min from engine/pyproject.toml as `3.13` (Python).
- Discovered related relation to github.com/Stirling-Tools/Stirling-PDF from README cross-link.
- This is an overlay record, not a maintainer-controlled canonical record.

- Left `repo.build` unset after deterministic escalation: no unique build/test candidate after deterministic tier walk. Preserved 2 candidate command(s) in `repo.build_candidates` instead of discarding them.
- Left `repo.test` unset after deterministic escalation: no unique build/test candidate after deterministic tier walk. Preserved 2 candidate command(s) in `repo.test_candidates` instead of discarding them.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
