# Evidence

- Imported repository name from README.md.
- Imported the security reporting channel from SECURITY.md.
- Inferred fallback values for `repo.description` because the imported files did not provide enough structured metadata.
- Left `repo.build` unset because `.github/workflows/ci_macos.yaml`, `.github/workflows/ci_python.yaml`, `.github/workflows/ci_ubuntu.yaml`, `.github/workflows/ci_windows.yaml`, and `.github/workflows/coverity-scan.yaml` suggested conflicting build commands.
- Left `repo.test` unset because `.github/workflows/ci_macos.yaml`, `.github/workflows/ci_ubuntu.yaml`, `.github/workflows/ci_webui.yaml`, and `.github/workflows/ci_windows.yaml` suggested conflicting test commands.
- This is an overlay record, not a maintainer-controlled canonical record.

- Left `repo.build` unset after deterministic escalation: no unique build/test candidate after deterministic tier walk.
- Left `repo.test` unset after deterministic escalation: no unique build/test candidate after deterministic tier walk.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Filled repo.description from GitHub repository metadata when the README surface did not provide one.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
