# Evidence

- Imported repository name, description, and docs entry points from README.md.
- Imported the security reporting channel from SECURITY.md.
- Left `repo.build` unset because `.github/workflows/copilot-setup-steps.yml`, `.github/workflows/create_test_report.yml`, `.github/workflows/infra.yml`, `.github/workflows/publish_extension.yml`, `.github/workflows/publish_release.yml`, `.github/workflows/publish_release_docker.yml`, `.github/workflows/roll_browser_into_playwright.yml`, and `package.json` suggested conflicting build commands.
- Imported repo.test from package.json as `npm test`.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
