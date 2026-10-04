# Evidence

- Inferred fallback values for `repo.name` and `repo.description` because the imported files did not provide enough structured metadata.
- Inferred repo.build from CliWrap.Benchmarks/CliWrap.Benchmarks.csproj as `dotnet build`.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Fresh verification

Prior verified authority was not inherited: this refresh must qualify using its current field scores.

## Command semantic correction (2026-10-03)

2026-10-03 semantic audit withheld repo.build pending command context or usable upstream instructions; repository-default applicability remains unresolved. Source inspection timestamps are unchanged.

- Withheld `repo.build` previously extracted from `CliWrap.Benchmarks/CliWrap.Benchmarks.csproj` as `dotnet build`. Component command lacks repository-default scope and working directory.
