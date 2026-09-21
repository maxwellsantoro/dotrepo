# Evidence

- Imported repository name and docs entry points from README.md.
- Imported the security reporting channel from SECURITY.md. SECURITY.md provided a policy or reporting URL rather than a direct mailbox, so `security_contact` preserves that URL.
- Inferred repo.build from build.gradle as `./gradlew build`.
- Inferred repo.test from .github/workflows/run_tests.yml as `./gradlew test`.
- Discovered related relation to github.com/termux/termux-app from README cross-link.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Documentation correction (2026-09-21T04:36:55.205964Z)

- Withheld docs.root; rejected `https://iterm2.com/documentation.html` because iTerm2 documentation belongs to a different terminal application. Source: [README.md:189](https://github.com/termux/termux-app/blob/084d709fbf23ea83b5cb85fd3d795c775be06676/README.md#L189). No replacement was established by this correction.
- This documentation-only correction advances the record timestamp. Older assessments for other fields retain their original check times and are invalidated by public export until fresh verification; their values were not refreshed.
- This is an overlay record, not a maintainer-controlled canonical record.
