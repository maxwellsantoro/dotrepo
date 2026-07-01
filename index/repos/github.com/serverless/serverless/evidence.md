# Evidence

- Imported repository name, description, and docs entry points from README.md.
- Imported the security reporting channel from SECURITY.md. SECURITY.md provided a policy or reporting URL rather than a direct mailbox, so `security_contact` preserves that URL.
- Left `repo.build` unset because `.github/workflows/ci-binary-installer.yml`, `.github/workflows/ci-framework.yml`, `.github/workflows/release-binary-installer.yml`, and `.github/workflows/release-framework.yml` suggested conflicting build commands.
- Imported repo.test from package.json as `npm test`.
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.build` to `npm run build` from `.github/workflows/ci-framework.yml` after model escalation.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
