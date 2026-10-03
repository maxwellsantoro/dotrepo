# Evidence

- Imported repository name and docs entry points from README.md.
- Imported repo.build from package.json as `npm run build`.
- Imported repo.toolchain.min from package.json as `14.0.0` (Node.js).
- Discovered related relation to github.com/vuejs/docs-next from README cross-link.
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.name` to `v2.vuejs.org` from `GitHub API` after deterministic escalation.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Auto-promotion

All fields are high-confidence present or high-confidence absent. Record auto-promoted to verified status.

## Documentation correction (2026-09-21T04:36:55.205964Z)

- Withheld docs.root; rejected `https://github.com/vuejs-id/docs` because Indonesian translation repository link is not the main documentation entry point. Source: [README.md:121](https://github.com/vuejs/v2.vuejs.org/blob/e468cc04e4da67ea758682609fc85e721916e7cf/README.md#L121). No replacement was established by this correction.
- Downgraded prior `verified` status to `inferred`: the withheld documentation field remains unresolved; prior verification is not inherited.
- This documentation-only correction advances the record timestamp. Older assessments for other fields retain their original check times and are invalidated by public export until fresh verification; their values were not refreshed.
- This is an overlay record, not a maintainer-controlled canonical record.
