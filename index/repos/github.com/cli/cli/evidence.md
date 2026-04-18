# Evidence

- Imported repository name and description from README.md.
- Imported maintainer candidates from CODEOWNERS. Maintainer information was imported from broad CODEOWNERS patterns; `owners.team` prefers `@cli/code-reviewers` from the repo-wide rule, and `owners.maintainers` preserves narrower owner candidates.
- Imported the security reporting channel from SECURITY.md. SECURITY.md provided a policy or reporting URL rather than a direct mailbox, so `security_contact` preserves that URL.
- Left `repo.build` unset because `go.mod` and `.github/workflows/go.yml` suggested conflicting build commands.
- Left `repo.test` unset because `go.mod` and `.github/workflows/go.yml` suggested conflicting test commands.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
