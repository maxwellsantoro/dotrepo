# Evidence

- Imported repository name and docs entry points from README.md.
- Inferred repo.build from .github/workflows/examples.yml as `yarn build:examples`.
- Imported repo.test from package.json as `yarn test`.
- Imported repo.toolchain.min from package.json as `10.13.0` (Node.js).
- Discovered related relation to github.com/webpack/webpack from package.json repository.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Downgrade guard

A prior verified status was preserved because no previously present field regressed in this refresh.
