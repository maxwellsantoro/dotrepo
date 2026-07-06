# Evidence

- Imported repository name from README.md.
- Imported the security reporting channel from SECURITY.md.
- Inferred fallback values for `repo.description` because the imported files did not provide enough structured metadata.
- Left `repo.build` unset because `.github/workflows/ci_macos.yaml`, `.github/workflows/ci_python.yaml`, `.github/workflows/ci_ubuntu.yaml`, `.github/workflows/ci_windows.yaml`, and `.github/workflows/coverity-scan.yaml` suggested conflicting build commands.
- Inferred repo.test from .github/workflows/ci_ubuntu.yaml as `cmake --build build --target check`.
- This is an overlay record, not a maintainer-controlled canonical record.

- Left `repo.build` unset after deterministic escalation: no unique build/test candidate after deterministic tier walk. Preserved 3 candidate command(s) in `repo.build_candidates` instead of discarding them.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
