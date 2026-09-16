# Evidence

- Imported repository name from README.md.
- Imported SECURITY.md, but no explicit contact channel was parsed, so security_contact = "unknown" is intentional.
- Inferred fallback values for `repo.description` because the imported files did not provide enough structured metadata.
- Imported repo.build from Makefile as `make build`.
- Imported repo.test from Makefile as `make test`.
- Imported repo.toolchain.min from go.mod as `1.25.0` (Go).
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

## Security contact evidence refresh (2026-09-16)

- Replaced `owners.security_contact = "unknown"` with `evilsocket@gmail.com`.
- Source: [SECURITY.md at `8eca2820f3c41d2004434ed5a291d87462caeeb7`](https://github.com/bettercap/bettercap/blob/8eca2820f3c41d2004434ed5a291d87462caeeb7/SECURITY.md), fetched at the pinned commit on 2026-09-16.
- Normalized the explicitly documented mailbox `evilsocket AT gmail DOT com` to `evilsocket@gmail.com`; no address was guessed.
- This is a field-scoped correction supported by the above evidence, not a full repository recrawl. Existing crawl timestamps and GitHub head metadata describe the earlier full crawl. This supersedes the earlier contact-absence conclusion; record authority is unchanged.
