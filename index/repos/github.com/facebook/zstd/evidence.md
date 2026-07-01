# Evidence

- Imported repository name and description from README.md.
- Imported the security reporting channel from SECURITY.md. SECURITY.md provided a policy or reporting URL rather than a direct mailbox, so `security_contact` preserves that URL.
- Left `repo.build` unset because `.github/workflows/cmake-tests.yml`, `.github/workflows/commit.yml`, `.github/workflows/dev-long-tests.yml`, and `.github/workflows/dev-short-tests.yml` suggested conflicting build commands.
- Left `repo.test` unset because `.github/workflows/commit.yml`, `.github/workflows/dev-long-tests.yml`, `.github/workflows/dev-short-tests.yml`, and `.github/workflows/nightly.yml` suggested conflicting test commands.
- Discovered related relation to github.com/Cyan4973/FiniteStateEntropy from README cross-link.
- This is an overlay record, not a maintainer-controlled canonical record.

- Left `repo.build` unset after deterministic escalation: no unique build/test candidate after deterministic tier walk.
- Left `repo.test` unset after deterministic escalation: no unique build/test candidate after deterministic tier walk.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
