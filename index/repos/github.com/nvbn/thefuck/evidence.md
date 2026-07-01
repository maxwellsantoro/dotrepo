# Evidence

- Imported repository name, description, and docs entry points from README.md.
- Inferred repo.test from .github/workflows/test.yml as `coverage run --source=thefuck,tests -m pytest -v --capture=sys tests`.
- Discovered related relation to github.com/skycocker/chromebrew from README cross-link.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Downgrade guard

A prior verified status was preserved because no previously present field regressed in this refresh.
