# Evidence

- Imported repository name from README.md.
- Imported SECURITY.md, but no explicit contact channel was parsed, so security_contact = "unknown" is intentional.
- Inferred repo.build from go.mod as `go build ./...`.
- Imported repo.test from README.md as `go test ./...`.
- Imported repo.toolchain.min from go.mod as `1.27` (Go).
- Discovered related relation to github.com/pocketbase/js-sdk from README cross-link.
- This is an overlay record, not a maintainer-controlled canonical record.

- Deepened `owners.security_contact` from `README.md` during deterministic escalation.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Fresh verification

Prior verified authority was not inherited: this refresh must qualify using its current field scores.
