# Evidence

- Imported repository name and docs entry points from README.md.
- Imported maintainer candidates from CODEOWNERS. Maintainer information was imported from broad CODEOWNERS patterns with multiple team owners, so `owners.team` was left unset and `owners.maintainers` preserves the competing owner candidates.
- Imported the security reporting channel from SECURITY.md. SECURITY.md provided a policy or reporting URL rather than a direct mailbox, so `security_contact` preserves that URL.
- Ignored component-scoped commands from `python/pyproject.toml` as repository defaults.
- Ignored component-scoped commands from `dotnet/src/SemanticKernel.Abstractions/SemanticKernel.Abstractions.csproj` as repository defaults.
- Imported repo.toolchain.min from python/pyproject.toml as `3.10` (Python).
- Imported docs.root as `https://aka.ms/sk/learn`. Explicit documentation link at README.md:345: - Read the [documentation](https://aka.ms/sk/learn)
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Auto-promotion

All fields are high-confidence present or high-confidence absent. Record auto-promoted to verified status.
