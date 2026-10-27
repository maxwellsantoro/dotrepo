# Evidence

- Imported repository name and docs entry points from README.md.
- Imported the security reporting channel from SECURITY.md. SECURITY.md provided a policy or reporting URL rather than a direct mailbox, so `security_contact` preserves that URL.
- Imported repo.build from Makefile as `make dist`.
- Imported repo.test from Makefile as `make test-unit`.
- Imported repo.toolchain.min from go.mod as `1.27.0` (Go).
- Imported docs.root as `https://doc.traefik.io/traefik/`. Explicit documentation link at README.md:89: You can find the complete documentation of Traefik v3 at [https://doc.traefik.io/traefik/](https://doc.traefik.io/traefik/).
- Conflicting documentation declarations in README.md; abstained from docs.getting_started.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Fresh verification

Prior verified authority was not inherited: this refresh must qualify using its current field scores.
