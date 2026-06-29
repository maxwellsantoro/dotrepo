# Evidence

- Imported repository name and description from README.md.
- Imported the security reporting channel from SECURITY.md.
- Left `repo.build` unset because `.github/workflows/build-and-test-pr.yml`, `.github/workflows/build-and-test-scheduled-3.1.yml`, `.github/workflows/build-and-test-scheduled-3.2.yml`, `.github/workflows/build-and-test-scheduled-3.3.yml`, and `.github/workflows/release-test.yml` suggested conflicting build commands.
- Left `repo.test` unset because `.github/workflows/build-and-test-pr.yml`, `.github/workflows/build-and-test-scheduled-3.1.yml`, `.github/workflows/build-and-test-scheduled-3.2.yml`, `.github/workflows/build-and-test-scheduled-3.3.yml`, and `.github/workflows/release-test.yml` suggested conflicting test commands.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Auto-promotion

All fields are high-confidence present or high-confidence absent. Record auto-promoted to verified status.
