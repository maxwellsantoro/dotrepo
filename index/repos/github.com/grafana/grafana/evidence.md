# Evidence

- Imported repository name, description, and docs entry points from README.md.
- Imported maintainer candidates from CODEOWNERS. Maintainer information was imported from broad CODEOWNERS patterns with multiple team owners, so `owners.team` was left unset and `owners.maintainers` preserves the competing owner candidates.
- Left `repo.build` unset because `package.json` and `go.mod` suggested conflicting build commands.
- Left `repo.test` unset because `package.json` and `go.mod` suggested conflicting test commands.
- This is an overlay record, not a maintainer-controlled canonical record.

- Left `repo.build` unset after model escalation: The candidates represent mutually exclusive technology stacks (Node.js vs Go) within the same repository context; no single primary build command can represent both..
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
