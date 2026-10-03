# Evidence

- Imported repository name and docs entry points from README.md.
- Imported maintainer candidates from CODEOWNERS.
- Imported SECURITY.md, but no explicit contact channel was parsed, so security_contact = "unknown" is intentional.
- Inferred repo.build from Cargo.toml as `cargo build --workspace`.
- Inferred repo.test from Cargo.toml as `cargo test --workspace`.
- Imported repo.toolchain.min from Cargo.toml as `1.96.1` (Rust).
- Discovered related relation to github.com/dani-garcia/vaultwarden from README cross-link.
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.name` to `vaultwarden` from `GitHub API` after deterministic escalation.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Fresh verification

Prior verified authority was not inherited: this refresh must qualify using its current field scores.

## Documentation correction (2026-09-21T04:36:55.205964Z)

- Withheld docs.getting_started; rejected `https://bitwarden.com/help/getting-started-organizations/` because Bitwarden organizations feature documentation is not Vaultwarden installation documentation. Source: [README.md:38](https://github.com/dani-garcia/vaultwarden/blob/eb212e23fad88e6136723f43e5b73543fa7026d3/README.md#L38). No replacement was established by this correction.
- This documentation-only correction advances the record timestamp. Older assessments for other fields retain their original check times and are invalidated by public export until fresh verification; their values were not refreshed.
- This is an overlay record, not a maintainer-controlled canonical record.
