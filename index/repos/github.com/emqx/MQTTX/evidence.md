# Evidence

- Imported repository name and docs entry points from README.md.
- Imported repo.build from package.json as `npm run build`.
- Left `repo.test` unset because `.github/workflows/units_test_cli.yaml` and `.github/workflows/units_test_desktop.yaml` suggested conflicting test commands.
- Imported repo.toolchain.min from package.json as `18` (Node.js).
- Discovered related relation to github.com/emqx/MQTTX from package.json repository.
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.name` to `MQTTX` from `GitHub API` after deterministic escalation.
- Left `repo.test` unset after model escalation: Both candidates are primary CI workflows targeting different components (cli vs desktop) with no clear hierarchy or single primary test command defined for the entire repository.. Preserved 2 candidate command(s) in `repo.test_candidates` instead of discarding them.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
