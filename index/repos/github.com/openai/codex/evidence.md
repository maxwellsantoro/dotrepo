# Evidence

- Imported repository name from README.md.
- Imported maintainer candidates from CODEOWNERS. Maintainer information was imported from CODEOWNERS; `owners.team` is `@openai/codex-core-agent-team` because it is the clearest imported team signal, but `owners.maintainers` still preserves narrower owner candidates.
- Imported the security reporting channel from SECURITY.md. SECURITY.md provided a policy or reporting URL rather than a direct mailbox, so `security_contact` preserves that URL.
- Inferred repo.build from codex-rs/Cargo.toml as `cargo build --workspace`.
- Imported repo.test from justfile as `just test`.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Downgrade guard

A prior verified status was preserved because no previously present field regressed in this refresh.
