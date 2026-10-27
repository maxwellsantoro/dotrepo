# Evidence

- Imported repository name and docs entry points from README.md.
- Imported the security reporting channel from SECURITY.md.
- Inferred repo.build from go.mod as `go build ./...`.
- Inferred repo.test from go.mod as `go test ./...`.
- Imported repo.toolchain.min from go.mod as `1.26.2` (Go).
- Imported docs.root as `https://docs.syncthing.net/`. Explicit documentation link at README.md:93: Please see the Syncthing [documentation site][6] [[source]][17].
- Imported docs.getting_started as `https://docs.syncthing.net/intro/getting-started.html`. Explicit documentation link at README.md:56: Take a look at the [getting started guide][2].
- Discovered related relation to github.com/syncthing/syncthing from README cross-link.
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.name` to `syncthing` from `GitHub API` after deterministic escalation.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
