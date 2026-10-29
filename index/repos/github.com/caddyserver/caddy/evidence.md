# Evidence

- Imported repository name and docs entry points from README.md.
- Imported the security reporting channel from SECURITY.md. SECURITY.md provided a policy or reporting URL rather than a direct mailbox, so `security_contact` preserves that URL.
- Inferred repo.build from go.mod as `go build ./...`.
- Inferred repo.test from go.mod as `go test ./...`.
- Imported repo.toolchain.min from go.mod as `1.26.0` (Go).
- Imported docs.root as `https://caddyserver.com/docs/`. Explicit documentation link at README.md:17: <a href="https://caddyserver.com/docs/">Documentation</a> ·
- Imported docs.getting_started as `https://caddyserver.com/docs/getting-started`. Explicit documentation link at README.md:168: **We recommend that all users -- regardless of experience level -- do our [Getting Started](https://caddyserver.com/docs/getting-started) guide to become familiar with using Caddy.**
- Discovered related relation to github.com/caddyserver/caddy from README cross-link.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
