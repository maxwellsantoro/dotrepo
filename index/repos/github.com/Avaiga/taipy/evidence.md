# Evidence

- Imported repository name and docs entry points from README.md.
- Imported the security reporting channel from SECURITY.md. SECURITY.md provided a policy or reporting URL rather than a direct mailbox, so `security_contact` preserves that URL.
- Imported repo.build from frontend/taipy-gui/package.json as `npm run build`.
- Imported repo.test from frontend/taipy-gui/package.json as `npm test`.
- Imported repo.toolchain.min from pyproject.toml as `3.9` (Python).
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Auto-promotion

All fields are high-confidence present or high-confidence absent. Record auto-promoted to verified status.

## Documentation correction (2026-09-21T04:36:55.205964Z)

- Corrected evidence for docs.getting_started as `https://docs.taipy.io/en/latest/tutorials/getting_started/installation/`: book announcement image is not an installation guide. Source: [README.md:118](https://github.com/Avaiga/taipy/blob/5bcb5749521f9ddcc725c009aca00a88ff724e87/README.md#L118).
- This documentation-only correction advances the record timestamp. Older assessments for other fields retain their original check times and are invalidated by public export until fresh verification; their values were not refreshed.
- This is an overlay record, not a maintainer-controlled canonical record.

## Command semantic correction (2026-10-03)

2026-10-03 semantic audit withheld repo.build, repo.test pending command context or usable upstream instructions; repository-default applicability remains unresolved. Source inspection timestamps are unchanged.

- Withheld `repo.build` previously extracted from `frontend/taipy-gui/package.json` as `npm run build`. Component command lacks repository-default scope and working directory.
- Withheld `repo.test` previously extracted from `frontend/taipy-gui/package.json` as `npm test`. Component command lacks repository-default scope and working directory.

Other retained field provenance includes inferred defaults; this correction does not verify their usability.
