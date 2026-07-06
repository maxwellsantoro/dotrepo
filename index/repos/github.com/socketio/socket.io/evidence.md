# Evidence

- Imported repository name and docs entry points from README.md.
- Imported the security reporting channel from SECURITY.md. SECURITY.md provided a policy or reporting URL rather than a direct mailbox, so `security_contact` preserves that URL.
- Left `repo.build` unset because `.github/workflows/build-examples.yml`, `.github/workflows/ci-engine.io-client.yml`, `.github/workflows/ci-engine.io-parser.yml`, `.github/workflows/ci-engine.io.yml`, `.github/workflows/ci-socket.io-adapter.yml`, `.github/workflows/ci-socket.io-client.yml`, `.github/workflows/ci-socket.io-cluster-adapter.yml`, and `.github/workflows/ci-socket.io-cluster-engine.yml` suggested conflicting build commands.
- Imported repo.test from CONTRIBUTING.md as `npm test -ws`.
- This is an overlay record, not a maintainer-controlled canonical record.

- Left `repo.build` unset after deterministic escalation: no unique build/test candidate after deterministic tier walk. Preserved 4 candidate command(s) in `repo.build_candidates` instead of discarding them.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
