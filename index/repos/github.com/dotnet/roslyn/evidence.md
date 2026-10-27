# Evidence

- Imported repository name and docs entry points from README.md.
- Imported maintainer candidates from CODEOWNERS. Maintainer information was imported from broad CODEOWNERS patterns with multiple team owners, so `owners.team` was left unset and `owners.maintainers` preserves the competing owner candidates.
- Imported the security reporting channel from SECURITY.md.
- Ignored component-scoped commands from `eng/eng.sln` as repository defaults.
- Imported docs.root as `https://docs.microsoft.com/en-us/dotnet/csharp/roslyn-sdk/compiler-api-model`. Explicit documentation link at README.md:41: Visit [Roslyn Architecture Overview](https://docs.microsoft.com/en-us/dotnet/csharp/roslyn-sdk/compiler-api-model) to get started with Roslyn’s API’s.
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.name` to `roslyn` from `GitHub API` after deterministic escalation.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Auto-promotion

All fields are high-confidence present or high-confidence absent. Record auto-promoted to verified status.
