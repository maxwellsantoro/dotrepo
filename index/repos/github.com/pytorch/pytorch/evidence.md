# Evidence

- Imported repository name and docs entry points from README.md.
- Imported maintainer candidates from CODEOWNERS. Maintainer information was imported from CODEOWNERS; `owners.team` is `@pytorch/pytorch-dev-infra` because it is the clearest imported team signal, but `owners.maintainers` still preserves narrower owner candidates.
- Imported the security reporting channel from SECURITY.md. SECURITY.md provided a policy or reporting URL rather than a direct mailbox, so `security_contact` preserves that URL.
- Imported repo.build from Makefile as `make all`.
- Imported repo.test from CONTRIBUTING.md as `pytest test/test_nn.py -k Loss -v`.
- Imported repo.toolchain.min from pyproject.toml as `3.10` (Python).
- Discovered related relation to github.com/twitter/torch-autograd from README cross-link.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Security contact normalization (2026-07-08)

Replaced non-actionable `security_contact` value `https://github.com/pytorch/pytorch/issues/new?template=bug-report.yml` with `unknown`. The prior URL was not an email or actionable vulnerability-reporting surface (promotion scoring: medium-present). Honest absence unblocks auto-publish without inventing a reporting channel.

## Auto-promotion

Record auto-promoted to verified: all fields are honestly resolved by deterministic promotion scoring.
