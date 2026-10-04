# Evidence

- Imported repository name and docs entry points from README.md.
- Imported maintainer candidates from CODEOWNERS. Maintainer information was imported from CODEOWNERS; `owners.team` is `@PowerShell/powershell-maintainers` because it is the clearest imported team signal, but `owners.maintainers` still preserves narrower owner candidates.
- Imported the security reporting channel from SECURITY.md. SECURITY.md provided a policy or reporting URL rather than a direct mailbox, so `security_contact` preserves that URL.
- Inferred fallback values for `repo.description` because the imported files did not provide enough structured metadata.
- Inferred repo.build from PowerShell.sln as `dotnet build`.
- Inferred repo.test from PowerShell.sln as `dotnet test`.
- Imported docs.getting_started as `https://learn.microsoft.com/powershell/scripting/learn/more-powershell-learning`. Explicit documentation link at README.md:21: If you are new to PowerShell and want to learn more, we recommend reviewing the [getting started][] documentation.
- Discovered related relation to github.com/discussions/quickstart from README cross-link.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
