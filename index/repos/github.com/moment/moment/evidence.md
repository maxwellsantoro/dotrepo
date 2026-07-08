# Evidence

- Imported repository name and docs entry points from README.md.
- Imported repo.test from package.json as `npm test`.
- Discovered related relation to github.com/moment/moment from package.json repository.
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.name` to `moment` from `GitHub API` after deterministic escalation.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Homepage normalization (2026-07-08)

Normalized scheme-less homepage to `https://momentjs.com` so URL quality gates treat it as a high-confidence absolute URL.

## Auto-promotion

Record auto-promoted to verified: all fields are honestly resolved by deterministic promotion scoring.
