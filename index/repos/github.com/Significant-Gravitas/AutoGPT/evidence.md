# Evidence

- Imported repository name, description, and docs entry points from README.md.
- Imported maintainer candidates from CODEOWNERS. Maintainer information was imported from broad CODEOWNERS patterns; `owners.team` prefers `@Significant-Gravitas/maintainers` from the repo-wide rule, and `owners.maintainers` preserves narrower owner candidates.
- Imported the security reporting channel from SECURITY.md. SECURITY.md provided a policy or reporting URL rather than a direct mailbox, so `security_contact` preserves that URL.
- Inferred repo.test from .github/workflows/classic-autogpt-ci.yml as `poetry run pytest -vv \`.
- Discovered related relation to github.com/Significant-Gravitas/AutoGPT from README cross-link.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Downgrade guard

A prior verified status was preserved because no previously present field regressed in this refresh.
