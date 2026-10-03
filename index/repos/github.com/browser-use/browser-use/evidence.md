# Evidence

- Imported repository name and docs entry points from README.md.
- Imported the security reporting channel from SECURITY.md. SECURITY.md provided a policy or reporting URL rather than a direct mailbox, so `security_contact` preserves that URL.
- Inferred repo.build from .github/workflows/install-script.yml as `python -m build --wheel`.
- Inferred repo.test from pyproject.toml as `python -m pytest`.
- Imported repo.toolchain.min from pyproject.toml as `3.11` (Python).
- Discovered related relation to github.com/browser-use/benchmark from README cross-link.
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.name` to `browser-use` from `GitHub API` after deterministic escalation.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
