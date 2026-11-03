# Evidence

- Imported repository name from README.md.
- Imported the security reporting channel from SECURITY.md. SECURITY.md provided a policy or reporting URL rather than a direct mailbox, so `security_contact` preserves that URL.
- Left `repo.build` unset because Go workflow execution context has unsupported structure in `.github/workflows/release-proposal.yml`, `.github/workflows/release.yml`; conventional commands cannot establish repository scope/setup.
- Left `repo.test` unset because Go workflow execution context has unsupported structure in `.github/workflows/release-proposal.yml`, `.github/workflows/release.yml`; conventional commands cannot establish repository scope/setup.
- Imported repo.toolchain.min from go.mod as `1.26.0` (Go).
- Discovered related relation to github.com/caddyserver/caddy from README cross-link.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
