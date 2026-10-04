# Evidence

- Imported repository name and docs entry points from README.md.
- Imported repo.build from managed_agents/roadtrip_planner/package.json as `npm run build`.
- Imported repo.test from tox.ini as `tox`.
- Imported repo.toolchain.min from pyproject.toml as `3.11` (Python).
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Auto-promotion

All fields are high-confidence present or high-confidence absent. Record auto-promoted to verified status.

## Command semantic correction (2026-10-03)

2026-10-03 semantic audit withheld repo.build pending command context or usable upstream instructions; prior auto-promotion is superseded. Source inspection timestamps are unchanged.

- Withheld `repo.build` previously extracted from `managed_agents/roadtrip_planner/package.json` as `npm run build`. Component command lacks repository-default scope and working directory.
