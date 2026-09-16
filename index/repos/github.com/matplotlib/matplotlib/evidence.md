# Evidence

- Imported repository name from README.md.
- Imported the security reporting channel from SECURITY.md. SECURITY.md provided a policy or reporting URL rather than a direct mailbox, so `security_contact` preserves that URL.
- Inferred repo.build from .github/workflows/cibuildwheel.yml as `python -m build --sdist`.
- Imported repo.test from tox.ini as `tox`.
- Imported repo.toolchain.min from pyproject.toml as `3.12` (Python).
- Discovered related relation to github.com/matplotlib/matplotlib from README cross-link.
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.name` to `matplotlib` from `GitHub API` after deterministic escalation.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Fresh verification

Prior verified authority was not inherited: this refresh must qualify using its current field scores.
