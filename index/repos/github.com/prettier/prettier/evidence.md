# Evidence

- Imported repository name, description, and docs entry points from README.md.
- Imported the security reporting channel from SECURITY.md. SECURITY.md provided a policy or reporting URL rather than a direct mailbox, so `security_contact` preserves that URL.
- Left `repo.build` unset because `package.json` and `.github/workflows/_build.yml` suggested conflicting build commands.
- Left `repo.test` unset because `.github/workflows/bundler-friendly.yml`, `.github/workflows/dev-package-test.yml`, `.github/workflows/dev-test.yml`, and `package.json` suggested conflicting test commands.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
