# Evidence

- Imported repository docs entry points from README.md.
- Imported the security reporting channel from SECURITY.md.
- Inferred fallback values for `repo.name` because the imported files did not provide enough structured metadata.
- Inferred repo.build from Scratch.sln as `dotnet build`.
- Inferred repo.test from Scratch.sln as `dotnet test`.
- Imported docs.root as `https://aka.ms/terminal-docs`. Explicit documentation link at README.md:299: All project documentation is located at [aka.ms/terminal-docs](https://aka.ms/terminal-docs). If you would like
- Discovered related relation to github.com/MicrosoftDocs/terminal from README cross-link.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
