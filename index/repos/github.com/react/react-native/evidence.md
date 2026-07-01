# Evidence

- Imported repository name, description, and docs entry points from README.md.
- Left `repo.build` unset because `package.json` and `build.gradle.kts` suggested conflicting build commands.
- Left `repo.test` unset because `package.json` and `build.gradle.kts` suggested conflicting test commands.
- This is an overlay record, not a maintainer-controlled canonical record.

- Left `repo.build` unset after model escalation: The candidates represent mutually exclusive build systems (Node.js/Yarn vs. JVM/Gradle); no single primary value can represent the repository.. Preserved 2 candidate command(s) in `repo.build_candidates` instead of discarding them.
- Left `repo.test` unset after model escalation: The candidates represent two different build systems (Node.js/Yarn vs. JVM/Gradle) with no indication of which one is the primary environment for this repository.. Preserved 2 candidate command(s) in `repo.test_candidates` instead of discarding them.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Downgrade guard

Status dropped from a prior verified record because the following previously present field(s) regressed: repo.build, repo.test.
