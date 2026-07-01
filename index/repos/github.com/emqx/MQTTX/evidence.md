# Evidence

- Imported repository name, description, and docs entry points from README.md.
- Imported repo.build from package.json as `npm run build`.
- Left `repo.test` unset because `.github/workflows/units_test_cli.yaml` and `.github/workflows/units_test_desktop.yaml` suggested conflicting test commands.
- Discovered related relation to github.com/emqx/MQTTX from package.json repository.
- This is an overlay record, not a maintainer-controlled canonical record.

- Left `repo.test` unset after model escalation: Both candidates are primary CI workflows for different components (cli vs desktop) with no clear hierarchy or single primary test command for the entire repository..
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
